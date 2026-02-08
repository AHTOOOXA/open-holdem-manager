from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class ImportResult(BaseModel):
    imported: int
    duplicates: int
    errors: int
    error_details: list[str] = []


class Settings(BaseModel):
    hero_username: str
    hero_site: str


class GraphPoint(BaseModel):
    hand_number: int
    cumulative_bb: float
    cumulative_ev_bb: float = 0.0
    cumulative_rake_bb: float = 0.0
    cumulative_showdown_bb: float = 0.0
    cumulative_nonshowdown_bb: float = 0.0
    cumulative_usd: float = 0.0
    cumulative_ev_usd: float = 0.0
    cumulative_rake_usd: float = 0.0
    cumulative_showdown_usd: float = 0.0
    cumulative_nonshowdown_usd: float = 0.0


class StatValue(BaseModel):
    value: float | None = None
    sample: int = 0


class PositionalStats(BaseModel):
    total: StatValue = StatValue()
    ep: StatValue = StatValue()
    mp: StatValue = StatValue()
    co: StatValue = StatValue()
    btn: StatValue = StatValue()
    sb: StatValue = StatValue()
    bb: StatValue = StatValue()


class HeroStats(BaseModel):
    hands: int = 0
    win_rate_bb100: float | None = None

    # Preflop
    vpip: PositionalStats = PositionalStats()
    pfr: PositionalStats = PositionalStats()
    open_raise: PositionalStats = PositionalStats()
    three_bet: PositionalStats = PositionalStats()
    three_bet_ip: StatValue = StatValue()
    three_bet_oop: StatValue = StatValue()
    four_bet: PositionalStats = PositionalStats()
    five_bet: StatValue = StatValue()
    fold_to_3bet: PositionalStats = PositionalStats()
    fold_to_4bet: PositionalStats = PositionalStats()
    call_open_raise: PositionalStats = PositionalStats()
    limp: PositionalStats = PositionalStats()
    squeeze: StatValue = StatValue()

    # Steal
    steal: PositionalStats = PositionalStats()
    fold_to_3bet_steal: StatValue = StatValue()
    four_bet_steal: StatValue = StatValue()
    vs_steal_fold: StatValue = StatValue()
    vs_steal_call: StatValue = StatValue()
    vs_steal_3bet: StatValue = StatValue()

    # Postflop
    cbet_flop: PositionalStats = PositionalStats()
    cbet_turn: PositionalStats = PositionalStats()
    cbet_river: PositionalStats = PositionalStats()
    fold_to_cbet_flop: PositionalStats = PositionalStats()
    fold_to_cbet_turn: PositionalStats = PositionalStats()
    fold_to_cbet_river: PositionalStats = PositionalStats()
    donk_bet_flop: StatValue = StatValue()

    # Aggression
    af_flop: StatValue = StatValue()
    af_turn: StatValue = StatValue()
    af_river: StatValue = StatValue()
    afq_flop: StatValue = StatValue()
    afq_turn: StatValue = StatValue()
    afq_river: StatValue = StatValue()

    # Missed cbet
    missed_cbet_flop: StatValue = StatValue()
    missed_cbet_turn: StatValue = StatValue()

    # Showdown
    wtsd: StatValue = StatValue()
    wsd: StatValue = StatValue()
    wwsf: StatValue = StatValue()
