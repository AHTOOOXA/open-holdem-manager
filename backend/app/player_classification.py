"""Player classification, workspace-scoped (one row per (player_id, workspace_id)).

Two independent outputs live in `player_classifications` (a separate table to avoid DuckDB FK
constraint issues with UPDATE on the referenced players table):

* ``player_type`` -- NIT/TAG/LAG/REC/MAN/UNK from VPIP/PFR ranges (legacy, unchanged).
* ``is_reg`` -- reg (TRUE) / fish (FALSE) by the configured RegRule (Configuration >
  Game types; app/config_sections.py). Base stats are the General screen's own counters, from
  the H2N bits of hand_players over hands H2N would import (``h2n_valid``):
    hands = valid player-hands in the workspace
    VPIP  = cases(V01) / opps(V01) * 100        PFR = cases(V02) / opps(V02) * 100
    limp  = cases(P22) / opps(P22) * 100  (limping possible = P22 opportunity; 0 when never)
    vpip_minus_pfr = VPIP% - PFR%  (difference of the two percentages)
  Evaluation: hands >= auto_reg_hands -> reg; hands < min_hands -> fish; else reg only when
  all four values lie inside their inclusive range (1e-6 tolerance). Players with no valid
  hands get NULL.
"""

from app.config_sections import RegRule, get_reg_rule
from app.stat_registry import VALID_SQL
from app.h2n.rows import sql_case, sql_opp

_EPS = 1e-6

_TYPE_SQL = """CASE
                    WHEN COUNT(*) < 20 THEN 'UNK'
                    WHEN SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 38
                         AND SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 28 THEN 'MAN'
                    WHEN SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 35
                         AND SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                             < SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) * 0.6 THEN 'REC'
                    WHEN SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 27
                         AND SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 20 THEN 'LAG'
                    WHEN SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) < 18
                         AND SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) < 14 THEN 'NIT'
                    WHEN SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) BETWEEN 18 AND 27
                         AND SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) BETWEEN 14 AND 22 THEN 'TAG'
                    ELSE 'UNK'
                END"""


def evaluate_reg(rule: RegRule, hands: int, vpip: float, pfr: float, limp: float) -> bool:
    """Reference implementation of the rule (the SQL below mirrors it)."""
    if hands >= rule.auto_reg_hands:
        return True
    if hands < rule.min_hands:
        return False

    def inside(v: float, r) -> bool:
        return r[0] - _EPS <= v <= r[1] + _EPS

    return (inside(vpip, rule.vpip) and inside(pfr, rule.pfr)
            and inside(vpip - pfr, rule.vpip_minus_pfr) and inside(limp, rule.limp))


def _reg_sql(rule: RegRule) -> str:
    """SELECT of (player_id, workspace_id, is_reg) over the (filtered) hand_players rows."""
    def rng(expr: str, r) -> str:
        return f"({expr}) BETWEEN {float(r[0]) - _EPS!r} AND {float(r[1]) + _EPS!r}"

    return f"""
        SELECT player_id, workspace_id,
            CASE WHEN hands >= {int(rule.auto_reg_hands)} THEN TRUE
                 WHEN hands < {int(rule.min_hands)} THEN FALSE
                 ELSE ({rng('vpip', rule.vpip)} AND {rng('pfr', rule.pfr)}
                       AND {rng('vpip - pfr', rule.vpip_minus_pfr)} AND {rng('limp', rule.limp)})
            END AS is_reg
        FROM (
            SELECT hp.player_id, hp.workspace_id, COUNT(*) AS hands,
                COALESCE(SUM({sql_case('V01')}) * 100.0 / NULLIF(SUM({sql_opp('V01')}), 0), 0) AS vpip,
                COALESCE(SUM({sql_case('V02')}) * 100.0 / NULLIF(SUM({sql_opp('V02')}), 0), 0) AS pfr,
                COALESCE(SUM({sql_case('P22')}) * 100.0 / NULLIF(SUM({sql_opp('P22')}), 0), 0) AS limp
            FROM hand_players hp
            WHERE {VALID_SQL} {{where}}
            GROUP BY hp.player_id, hp.workspace_id
        )"""


def batch_update_player_types(db, workspace_id: int | None = None) -> None:
    """Recompute player_type and is_reg.

    With workspace_id only that workspace is recomputed; None recomputes every workspace
    (full rebuild). Writes via DELETE + INSERT (DuckDB UPDATE is DELETE+INSERT and would hit
    FK constraints on referenced tables).
    """
    rule = get_reg_rule(db)
    where = "AND hp.workspace_id = ?" if workspace_id is not None else ""
    params = [workspace_id] if workspace_id is not None else []
    if workspace_id is not None:
        db.execute("DELETE FROM player_classifications WHERE workspace_id = ?", params)
    else:
        db.execute("DELETE FROM player_classifications")
    db.execute(f"""
        INSERT INTO player_classifications (player_id, workspace_id, player_type, is_reg)
        SELECT t.player_id, t.workspace_id, t.player_type, r.is_reg
        FROM (
            SELECT hp.player_id, hp.workspace_id, {_TYPE_SQL} AS player_type
            FROM hand_players hp
            WHERE TRUE {where}
            GROUP BY hp.player_id, hp.workspace_id
        ) t
        LEFT JOIN ({_reg_sql(rule).format(where=where)}) r
          ON r.player_id = t.player_id AND r.workspace_id = t.workspace_id
    """, params + params)
