"""Player type classification based on VPIP/PFR ranges.

Classifies players as NIT/TAG/LAG/REC/MAN/UNK based on aggregated stats.
Uses a separate player_classifications table to avoid DuckDB FK constraint
issues with UPDATE on the referenced players table.
"""


def classify_player(vpip: float, pfr: float, hands: int) -> str:
    """Classify a player based on VPIP/PFR percentages.

    First match wins. Returns one of: NIT, TAG, LAG, REC, MAN, UNK.
    """
    if hands < 20:
        return "UNK"
    if vpip > 38 and pfr > 28:
        return "MAN"
    if vpip > 35 and pfr < vpip * 0.6:
        return "REC"
    if vpip > 27 and pfr > 20:
        return "LAG"
    if vpip < 18 and pfr < 14:
        return "NIT"
    if 18 <= vpip <= 27 and 14 <= pfr <= 22:
        return "TAG"
    return "UNK"


def batch_update_player_types(db) -> None:
    """Recompute player_type for all players based on aggregated VPIP/PFR.

    Writes to player_classifications table (not players) to avoid DuckDB
    constraint errors — DuckDB implements UPDATE as DELETE+INSERT, which
    fails on tables referenced by foreign keys.
    """
    db.execute("DELETE FROM player_classifications")
    db.execute("""
        INSERT INTO player_classifications (player_id, player_type)
        SELECT
            hp.player_id,
            CASE
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
            END
        FROM hand_players hp
        GROUP BY hp.player_id
    """)
