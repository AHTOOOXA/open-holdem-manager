from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import Optional


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
    played_at: str = ""
    cumulative_bb: float
    cumulative_ev_bb: float = 0.0
    cumulative_rake_bb: float = 0.0
    cumulative_jackpot_bb: float = 0.0
    cumulative_showdown_bb: float = 0.0
    cumulative_nonshowdown_bb: float = 0.0
    cumulative_usd: float = 0.0
    cumulative_ev_usd: float = 0.0
    cumulative_rake_usd: float = 0.0
    cumulative_jackpot_usd: float = 0.0
    cumulative_showdown_usd: float = 0.0
    cumulative_nonshowdown_usd: float = 0.0


class VarianceStats(BaseModel):
    sd_bb: float  # per-hand standard deviation
    sd_bb100: float  # SD scaled to bb/100
    winrate_bb100: float
    ci_lower_bb100: float  # 95% CI lower bound
    ci_upper_bb100: float  # 95% CI upper bound
    n: int


class SessionMarker(BaseModel):
    start_hand: int
    end_hand: int
    start_time: str
    end_time: str


class GraphResponse(BaseModel):
    points: list[GraphPoint]
    sessions: list[SessionMarker] = []
    variance: VarianceStats | None = None


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
    win_rate_ev_bb100: float | None = None

    # Preflop
    vpip: PositionalStats = PositionalStats()
    pfr: PositionalStats = PositionalStats()
    open_raise: PositionalStats = PositionalStats()
    three_bet: PositionalStats = PositionalStats()
    three_bet_ip: PositionalStats = PositionalStats()
    three_bet_oop: PositionalStats = PositionalStats()
    four_bet: PositionalStats = PositionalStats()
    five_bet: StatValue = StatValue()
    fold_to_3bet: PositionalStats = PositionalStats()
    fold_to_4bet: PositionalStats = PositionalStats()
    call_open_raise: PositionalStats = PositionalStats()
    limp: PositionalStats = PositionalStats()
    limp_fold: StatValue = StatValue()
    squeeze: StatValue = StatValue()
    four_bet_range: StatValue = StatValue()
    four_bet_fold: StatValue = StatValue()
    call_4bet: StatValue = StatValue()
    bb_defense: StatValue = StatValue()
    iso_raise: StatValue = StatValue()
    fold_to_squeeze: StatValue = StatValue()

    # Steal
    steal: PositionalStats = PositionalStats()
    fold_to_3bet_steal: PositionalStats = PositionalStats()
    four_bet_steal: PositionalStats = PositionalStats()
    four_bet_fold_steal: PositionalStats = PositionalStats()
    vs_steal_fold: PositionalStats = PositionalStats()
    vs_steal_call: PositionalStats = PositionalStats()
    vs_steal_3bet: PositionalStats = PositionalStats()

    # Postflop
    cbet_flop: PositionalStats = PositionalStats()
    cbet_turn: PositionalStats = PositionalStats()
    cbet_river: PositionalStats = PositionalStats()
    fold_to_cbet_flop: PositionalStats = PositionalStats()
    fold_to_cbet_turn: PositionalStats = PositionalStats()
    fold_to_cbet_river: PositionalStats = PositionalStats()
    donk_bet_flop: StatValue = StatValue()
    donk_bet_turn: StatValue = StatValue()
    donk_bet_river: StatValue = StatValue()

    # vs CBet Flop by pot type
    fold_cbet_flop_raised: StatValue = StatValue()
    call_cbet_flop_raised: StatValue = StatValue()
    raise_cbet_flop_raised: StatValue = StatValue()
    fold_cbet_flop_3bet: StatValue = StatValue()
    call_cbet_flop_3bet: StatValue = StatValue()
    raise_cbet_flop_3bet: StatValue = StatValue()

    # Aggression
    af_flop: StatValue = StatValue()
    af_turn: StatValue = StatValue()
    af_river: StatValue = StatValue()
    afq_flop: StatValue = StatValue()
    afq_turn: StatValue = StatValue()
    afq_river: StatValue = StatValue()

    # Missed cbet
    missed_cbet_flop: StatValue = StatValue()
    missed_cbet_flop_ip: StatValue = StatValue()
    missed_cbet_flop_oop: StatValue = StatValue()
    missed_cbet_fold_ip: StatValue = StatValue()
    missed_cbet_fold_oop: StatValue = StatValue()
    missed_cbet_turn: StatValue = StatValue()

    # vs Missed cbet
    vs_missed_cbet: StatValue = StatValue()
    vs_missed_cbet_bet_ip: StatValue = StatValue()
    vs_missed_cbet_check_fold_ip: StatValue = StatValue()
    vs_missed_cbet_bet_oop_turn: StatValue = StatValue()
    vs_missed_cbet_check_fold_oop: StatValue = StatValue()

    # Showdown
    wtsd: StatValue = StatValue()
    wsd: StatValue = StatValue()
    wwsf: StatValue = StatValue()


# ── Hand Browser Models ──────────────────────────────────────────────

class ActionItem(BaseModel):
    a: str            # R(aise), B(et), C(all), X(check)
    v: Optional[int] = None  # amount in BB (rounded), None for X
    h: bool = False   # is hero action


class HandSummary(BaseModel):
    id: str
    played_at: datetime
    stakes: str
    game_mode: str = ""
    bb_amount: float
    position: str
    card1: Optional[str] = None
    card2: Optional[str] = None
    won_bb: float
    all_in_ev_bb: float = 0
    tags: list[str] = []
    preflop_actions: list[ActionItem] = []
    flop_cards: list[str] = []
    flop_pot: int = 0
    flop_actions: list[ActionItem] = []
    turn_card: Optional[str] = None
    turn_pot: int = 0
    turn_actions: list[ActionItem] = []
    river_card: Optional[str] = None
    river_pot: int = 0
    river_actions: list[ActionItem] = []


class HandListResponse(BaseModel):
    hands: list[HandSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class HandPlayerDetail(BaseModel):
    seat: int
    position: str
    username: str
    stack_bb: float
    card1: Optional[str] = None
    card2: Optional[str] = None
    won_bb: float
    is_hero: bool = False


class HandAction(BaseModel):
    street: str
    player: str
    position: str
    action: str
    amount_bb: Optional[float] = None
    is_all_in: bool = False
    is_hero: bool = False


class BoardCards(BaseModel):
    flop: list[str] = []
    turn: list[str] = []
    river: list[str] = []


class HandDetail(BaseModel):
    id: str
    played_at: datetime
    stakes: str
    bb_amount: float
    table_name: Optional[str] = None
    table_size: int
    raw_text: Optional[str] = None
    players: list[HandPlayerDetail] = []
    board: BoardCards = BoardCards()
    actions: list[HandAction] = []
    tags: list[str] = []
    note: Optional[str] = None


class TagCount(BaseModel):
    tag: str
    count: int


# ── Results Dashboard Models ─────────────────────────────────────────

class FilterOptions(BaseModel):
    stakes: list[str] = []
    game_modes: list[str] = []
    date_range: dict[str, str | None] = {}


class StakeBreakdown(BaseModel):
    stakes: str
    game_mode: str = ""
    bb_amount: float
    hands: int
    won_bb: float
    won_usd: float
    ev_bb: float
    rake_bb: float
    rake_usd: float
    jackpot_bb: float = 0.0
    jackpot_usd: float = 0.0
    bb_per_100: float
    ev_bb_per_100: float


class MonthBreakdown(BaseModel):
    month: str
    hands: int
    won_bb: float
    won_usd: float
    ev_bb: float
    rake_bb: float
    rake_usd: float
    jackpot_bb: float = 0.0
    jackpot_usd: float = 0.0
    bb_per_100: float
    ev_bb_per_100: float


class PositionBreakdown(BaseModel):
    position: str
    hands: int
    won_bb: float
    won_usd: float
    ev_bb: float
    rake_bb: float
    rake_usd: float
    jackpot_bb: float = 0.0
    jackpot_usd: float = 0.0
    bb_per_100: float
    ev_bb_per_100: float


class ResultsBreakdown(BaseModel):
    by_stakes: list[StakeBreakdown] = []
    by_month: list[MonthBreakdown] = []
    by_position: list[PositionBreakdown] = []


# ── Drift Detection Models ──────────────────────────────────────────

class DriftStat(BaseModel):
    stat: str
    lifetime_avg: float
    window_avg: float
    lifetime_n: int
    window_n: int
    drift_pct: float     # relative change: (window - lifetime) / lifetime * 100
    ci_lower: float      # 95% CI lower bound for window estimate
    ci_upper: float      # 95% CI upper bound for window estimate
    direction: str       # "up" or "down"
    interpretation: str  # human-readable meaning

class DriftResponse(BaseModel):
    stats: list[DriftStat] = []
    window_hands: int = 0
    total_hands: int = 0


# ── Range Page Models ────────────────────────────────────────────────

class ComboStats(BaseModel):
    combo: str  # e.g. "AKs", "AKo", "AA"
    hands: int
    vpip: int = 0
    pfr: int = 0
    three_bet: int = 0
    won_bb: float = 0.0
    ev_bb: float = 0.0
    bb_per_100: float = 0.0
    ev_bb_per_100: float = 0.0
    wtsd: int = 0
    wtsd_opp: int = 0  # saw flop count
    wsd: int = 0
    wsd_opp: int = 0  # went to showdown count


class RangeResponse(BaseModel):
    combos: list[ComboStats] = []
    total_hands: int = 0


# ── Cash Drop Models ────────────────────────────────────────────────

class CashDropSummary(BaseModel):
    total_hands: int
    cash_drop_hands: int       # hands with a cash drop at table
    eligible_hands: int        # hands where hero paid jackpot fee
    pots_won: int              # eligible pots hero won
    # Financials
    total_paid_bb: float       # actual jackpot fees paid
    total_paid_usd: float
    total_received_bb: float   # EV share of cash drops (1/table_size)
    total_received_usd: float
    net_bb: float
    net_usd: float
    frequency: float           # 1 drop every N hands
    avg_drop_bb: float         # avg full drop size in BB
    # Hero stats in cash drop pots
    hero_vpip_pct: float | None
    hero_pfr_pct: float | None
    hero_three_bet_pct: float | None
    hero_limp_pct: float | None
    hero_allin_raise_pct: float | None
    hero_allin_call_pct: float | None
    hero_wtsd_pct: float | None
    hero_wsd_pct: float | None
    hero_won_bb: float | None
    hero_bb100: float | None


class CashDropTypeBreakdown(BaseModel):
    drop_bb: float
    count: int
    total_usd: float


class CashDropRangeCategory(BaseModel):
    label: str
    combos: list[ComboStats]
    total_hands: int


class CashDropFieldStats(BaseModel):
    total_players: int         # total player-hand entries in cash drop pots
    avg_players_per_pot: float | None
    vpip_pct: float | None
    pfr_pct: float | None
    three_bet_pct: float | None
    limp_pct: float | None
    allin_raise_pct: float | None
    allin_call_pct: float | None
    wtsd_pct: float | None
    wsd_pct: float | None
    avg_won_bb: float | None   # avg bb won per hand (field)


class CashDropResponse(BaseModel):
    summary: CashDropSummary
    field: CashDropFieldStats | None = None
    by_type: list[CashDropTypeBreakdown]
    ranges: list[CashDropRangeCategory]


# ── Stat Detail Models ─────────────────────────────────────────────

# ── Stat Trend / Analysis Models ──────────────────────────────────────

class TrendPoint(BaseModel):
    hand_number: int
    rolling_pct: float
    sample: int


class StatTrendResponse(BaseModel):
    stat_key: str
    overall_pct: float
    points: list[TrendPoint]


class ResponseDistribution(BaseModel):
    fold_count: int
    call_count: int
    raise_count: int
    fold_pct: float
    call_pct: float
    raise_pct: float
    total: int


class StatAnalysisResponse(BaseModel):
    stat_key: str
    response_distribution: ResponseDistribution | None = None


# ── Stat Detail Models ─────────────────────────────────────────────

# ── Session Models ─────────────────────────────────────────────────

class SessionSummary(BaseModel):
    session_index: int
    start_time: str
    end_time: str
    hands: int
    duration_minutes: float
    stakes: list[str] = []
    won_bb: float
    won_usd: float
    ev_bb: float
    ev_usd: float
    rake_bb: float
    rake_usd: float
    bb_per_100: float
    ev_bb_per_100: float


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int


class SessionGraphPoint(BaseModel):
    hand_number: int
    played_at: str
    cumulative_bb: float
    cumulative_ev_bb: float
    cumulative_usd: float
    cumulative_ev_usd: float


class SessionStats(BaseModel):
    session_index: int
    start_time: str
    end_time: str
    hands: int
    duration_minutes: float
    stakes: list[str] = []
    won_bb: float
    won_usd: float
    ev_bb: float
    ev_usd: float
    rake_bb: float
    rake_usd: float
    bb_per_100: float
    ev_bb_per_100: float
    hands_per_hour: float
    usd_per_hour: float
    bb_per_hour: float
    vpip_pct: float | None = None
    pfr_pct: float | None = None
    three_bet_pct: float | None = None
    cbet_flop_pct: float | None = None
    wtsd_pct: float | None = None
    wsd_pct: float | None = None
    wwsf_pct: float | None = None
    steal_pct: float | None = None
    afq_flop_pct: float | None = None


class SessionBigHand(BaseModel):
    hand_id: str
    played_at: str
    won_bb: float
    won_usd: float
    position: str
    card1: Optional[str] = None
    card2: Optional[str] = None
    stakes: str


class SessionDetailResponse(BaseModel):
    session_index: int
    stats: SessionStats
    graph: list[SessionGraphPoint] = []
    biggest_wins: list[SessionBigHand] = []
    biggest_losses: list[SessionBigHand] = []


# ── Widget API Response Models ────────────────────────────────────────

class EvScenario(BaseModel):
    label: str
    bb_per_100: float
    hands: int
    total_won_bb: float

class EvBreakdownResponse(BaseModel):
    stat_key: str
    scenarios: list[EvScenario]
    overall_bb_per_100: float
    overall_hands: int

class SizingBucket(BaseModel):
    size_bb: float
    count: int
    pct: float

class SizingResponse(BaseModel):
    buckets: list[SizingBucket]
    avg_size_bb: float | None
    median_size_bb: float | None
    total: int

class FoldEquityResponse(BaseModel):
    fold_pct: float
    fold_count: int
    total: int

class ContextBucket(BaseModel):
    label: str
    actions: int
    opportunities: int
    pct: float | None

class ByContextResponse(BaseModel):
    dimension: str
    buckets: list[ContextBucket]

class CompositionSlice(BaseModel):
    label: str
    count: int
    pct: float

class CompositionResponse(BaseModel):
    slices: list[CompositionSlice]
    total: int

class MoneyResponse(BaseModel):
    total_bb: float
    hands: int
    bb_per_100: float

class PostflopBridgeResponse(BaseModel):
    cbet_pct: float | None
    cbet_count: int
    cbet_opp: int
    avg_spr: float | None

class ContinuingCombo(BaseModel):
    combo: str
    fold: int
    call: int
    raise_count: int  # 'raise' is reserved
    total: int

class ContinuingRangeResponse(BaseModel):
    combos: list[ContinuingCombo]
    total_hands: int


class StatRangeCombo(BaseModel):
    combo: str
    hands: int            # opportunity count for this combo
    actions: int          # action count
    won_bb: float         # total won_bb when action taken
    ev_bb: float          # total ev_bb when action taken
    bb_per_100: float     # bb/100 when action taken
    ev_bb_per_100: float  # ev bb/100 when action taken
    total_won_bb: float   # total won_bb across ALL hands (action + no-action)
    total_bb_per_100: float  # overall bb/100 for this combo


class StatRangeResponse(BaseModel):
    combos: list[StatRangeCombo] = []
    total_hands: int = 0
    total_actions: int = 0


class StatDetailHand(BaseModel):
    hand_id: str
    played_at: datetime
    position: str
    card1: Optional[str] = None
    card2: Optional[str] = None
    action_taken: bool
    won_bb: float
    stakes: str
    all_in_ev_bb: float = 0.0
    bb_amount: float = 0.0
    board_flop: list[str] = []
    board_turn: Optional[str] = None
    board_river: Optional[str] = None
    preflop_actions: list[ActionItem] = []
    flop_actions: list[ActionItem] = []
    flop_pot: int = 0
    turn_actions: list[ActionItem] = []
    turn_pot: int = 0
    river_actions: list[ActionItem] = []
    river_pot: int = 0
    key_street_actions: list[ActionItem] = []


class StatDetailHandsResponse(BaseModel):
    stat_key: str
    stat_name: str
    action_count: int
    opportunity_count: int
    key_street: Optional[str] = None
    hands: list[StatDetailHand]
    total: int
    page: int
    per_page: int
    total_pages: int
