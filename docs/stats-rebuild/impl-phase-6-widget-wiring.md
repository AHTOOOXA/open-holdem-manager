# Phase 6 Implementation — Widget Wiring

## Goal

Update stat detail page widget lists so existing widget components appear on the correct stat detail pages. Currently most stats outside the preflop section show a minimal widget list (often just `trend_sparkline`). The 17 widget component types are already implemented in `frontend/src/components/stats/widgets/`. This phase wires them up by:

1. Updating `frontend/src/lib/stat-registry.ts` widget arrays
2. Adding missing backend configs in `backend/app/stat_registry.py`

No new widget components. No new API endpoints. No new DB columns.

---

## 1. Frontend: `stat-registry.ts` Widget Array Updates

### Files to modify

- `frontend/src/lib/stat-registry.ts` — update `widgets` arrays in the `REGISTRY` object

### Complete change table

| Stat Key | Current Widgets | New Widgets |
|----------|----------------|-------------|
| **Steal section** | | |
| `steal` | `trend_sparkline` | `range_heatmap`, `fold_equity`, `ev_breakdown`, `villain_response`, `postflop_bridge`, `trend_sparkline` |
| `fold_to_steal` | `response_distribution`, `trend_sparkline` | `response_distribution`, `range_heatmap`, `by_context`, `ev_breakdown`, `trend_sparkline` |
| `call_steal` | `response_distribution`, `trend_sparkline` | `range_heatmap`, `ev_breakdown`, `postflop_bridge`, `by_context`, `trend_sparkline` |
| `three_bet_vs_steal` | `response_distribution`, `trend_sparkline` | `range_heatmap`, `fold_equity`, `ev_breakdown`, `by_context`, `trend_sparkline` |
| **Postflop: C-Bet** | | |
| `cbet_flop` | `positional_bar`, `trend_sparkline` | `response_distribution`, `ev_breakdown`, `sizing_histogram`, `by_context`, `positional_bar`, `trend_sparkline` |
| `cbet_turn` | `positional_bar`, `trend_sparkline` | `ev_breakdown`, `sizing_histogram`, `positional_bar`, `trend_sparkline` |
| `cbet_river` | `positional_bar`, `trend_sparkline` | `fold_equity`, `ev_breakdown`, `sizing_histogram`, `positional_bar`, `trend_sparkline` |
| **Postflop: Fold to C-Bet** | | |
| `fold_to_cbet_flop` | `positional_bar`, `response_distribution`, `trend_sparkline` | `response_distribution`, `ev_breakdown`, `by_context`, `positional_bar`, `trend_sparkline` |
| `fold_to_cbet_turn` | `positional_bar`, `response_distribution`, `trend_sparkline` | `response_distribution`, `ev_breakdown`, `positional_bar`, `trend_sparkline` |
| `fold_to_cbet_river` | `positional_bar`, `response_distribution`, `trend_sparkline` | `response_distribution`, `ev_breakdown`, `positional_bar`, `trend_sparkline` |
| **Showdown** | | |
| `went_to_showdown` | `trend_sparkline` | `by_context`, `ev_breakdown`, `trend_sparkline` |
| `won_at_showdown` | `trend_sparkline` | `by_context`, `ev_breakdown`, `trend_sparkline` |
| `wwsf` | `trend_sparkline` | `composition`, `by_context`, `trend_sparkline` |
| **Donk Bet** | | |
| `donk_bet_flop` | `trend_sparkline` | `ev_breakdown`, `range_heatmap`, `villain_response`, `trend_sparkline` |
| `donk_bet_turn` | `trend_sparkline` | `ev_breakdown`, `by_context`, `trend_sparkline` |
| `donk_bet_river` | `trend_sparkline` | `ev_breakdown`, `trend_sparkline` |
| **Aggression Factor** | | |
| `af_flop` | `trend_sparkline` | `by_context`, `ev_breakdown`, `trend_sparkline` |
| `af_turn` | `trend_sparkline` | `by_context`, `ev_breakdown`, `trend_sparkline` |
| `af_river` | `trend_sparkline` | `by_context`, `ev_breakdown`, `trend_sparkline` |
| **Aggression Frequency** | | |
| `afq_flop` | `trend_sparkline` | `by_context`, `trend_sparkline` |
| `afq_turn` | `trend_sparkline` | `by_context`, `trend_sparkline` |
| `afq_river` | `trend_sparkline` | `by_context`, `trend_sparkline` |
| **Iso Raise (reorder)** | | |
| `iso_raise` | `range_heatmap`, `by_context`, `sizing_histogram`, `ev_breakdown`, `trend_sparkline` | `fold_equity`, `ev_breakdown`, `by_context`, `trend_sparkline` |

### Stats to leave unchanged (already good)

- `vpip`, `pfr`, `open_raise`, `call_open_raise`, `three_bet`, `three_bet_ip`, `three_bet_oop`
- `four_bet`, `five_bet`, `fold_to_3bet`, `fold_to_4bet`, `limp`, `squeeze`
- `limp_fold`, `four_bet_fold`, `call_4bet`, `four_bet_range`
- `bb_defense`, `fold_to_squeeze`
- All `missed_cbet_*`, `vs_missed_cbet_*`, `saw_flop`
- `fold_cbet_flop_raised`, `call_cbet_flop_raised`, `raise_cbet_flop_raised`
- `fold_cbet_flop_3bet`, `call_cbet_flop_3bet`, `raise_cbet_flop_3bet`
- `four_bet_fold_steal`

### Exact code changes

#### Steal section (lines 57-60)

```typescript
// Before:
steal:             { displayName: 'Steal',             heroStatsField: 'steal',             isPositional: true,  widgets: ['trend_sparkline'] },
fold_to_steal:     { displayName: 'Fold to Steal',     heroStatsField: 'vs_steal_fold',     isPositional: true,  widgets: ['response_distribution', 'trend_sparkline'] },
call_steal:        { displayName: 'Call Steal',        heroStatsField: 'vs_steal_call',     isPositional: true,  widgets: ['response_distribution', 'trend_sparkline'] },
three_bet_vs_steal:{ displayName: '3-Bet vs Steal',   heroStatsField: 'vs_steal_3bet',     isPositional: true,  widgets: ['response_distribution', 'trend_sparkline'] },

// After:
steal:             { displayName: 'Steal',             heroStatsField: 'steal',             isPositional: true,  widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'villain_response', 'postflop_bridge', 'trend_sparkline'] },
fold_to_steal:     { displayName: 'Fold to Steal',     heroStatsField: 'vs_steal_fold',     isPositional: true,  widgets: ['response_distribution', 'range_heatmap', 'by_context', 'ev_breakdown', 'trend_sparkline'] },
call_steal:        { displayName: 'Call Steal',        heroStatsField: 'vs_steal_call',     isPositional: true,  widgets: ['range_heatmap', 'ev_breakdown', 'postflop_bridge', 'by_context', 'trend_sparkline'] },
three_bet_vs_steal:{ displayName: '3-Bet vs Steal',   heroStatsField: 'vs_steal_3bet',     isPositional: true,  widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'by_context', 'trend_sparkline'] },
```

#### Postflop C-Bet (lines 64-66)

```typescript
// Before:
cbet_flop:         { displayName: 'C-Bet Flop',       heroStatsField: 'cbet_flop',         isPositional: true,  widgets: ['positional_bar', 'trend_sparkline'] },
cbet_turn:         { displayName: 'C-Bet Turn',       heroStatsField: 'cbet_turn',         isPositional: true,  widgets: ['positional_bar', 'trend_sparkline'] },
cbet_river:        { displayName: 'C-Bet River',      heroStatsField: 'cbet_river',        isPositional: true,  widgets: ['positional_bar', 'trend_sparkline'] },

// After:
cbet_flop:         { displayName: 'C-Bet Flop',       heroStatsField: 'cbet_flop',         isPositional: true,  widgets: ['response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'positional_bar', 'trend_sparkline'] },
cbet_turn:         { displayName: 'C-Bet Turn',       heroStatsField: 'cbet_turn',         isPositional: true,  widgets: ['ev_breakdown', 'sizing_histogram', 'positional_bar', 'trend_sparkline'] },
cbet_river:        { displayName: 'C-Bet River',      heroStatsField: 'cbet_river',        isPositional: true,  widgets: ['fold_equity', 'ev_breakdown', 'sizing_histogram', 'positional_bar', 'trend_sparkline'] },
```

#### Postflop Fold to C-Bet (lines 68-70)

```typescript
// Before:
fold_to_cbet_flop: { displayName: 'Fold to CBet Flop',heroStatsField: 'fold_to_cbet_flop', isPositional: true,  widgets: ['positional_bar', 'response_distribution', 'trend_sparkline'] },
fold_to_cbet_turn: { displayName: 'Fold to CBet Turn',heroStatsField: 'fold_to_cbet_turn', isPositional: true,  widgets: ['positional_bar', 'response_distribution', 'trend_sparkline'] },
fold_to_cbet_river:{ displayName: 'Fold to CBet River',heroStatsField:'fold_to_cbet_river', isPositional: true,  widgets: ['positional_bar', 'response_distribution', 'trend_sparkline'] },

// After:
fold_to_cbet_flop: { displayName: 'Fold to CBet Flop',heroStatsField: 'fold_to_cbet_flop', isPositional: true,  widgets: ['response_distribution', 'ev_breakdown', 'by_context', 'positional_bar', 'trend_sparkline'] },
fold_to_cbet_turn: { displayName: 'Fold to CBet Turn',heroStatsField: 'fold_to_cbet_turn', isPositional: true,  widgets: ['response_distribution', 'ev_breakdown', 'positional_bar', 'trend_sparkline'] },
fold_to_cbet_river:{ displayName: 'Fold to CBet River',heroStatsField:'fold_to_cbet_river', isPositional: true,  widgets: ['response_distribution', 'ev_breakdown', 'positional_bar', 'trend_sparkline'] },
```

#### Donk Bet (lines 79-81)

```typescript
// Before:
donk_bet_flop:     { displayName: 'Donk Bet Flop',    heroStatsField: 'donk_bet_flop',     isPositional: false, widgets: ['trend_sparkline'] },
donk_bet_turn:     { displayName: 'Donk Bet Turn',    heroStatsField: 'donk_bet_turn',     isPositional: false, widgets: ['trend_sparkline'] },
donk_bet_river:    { displayName: 'Donk Bet River',   heroStatsField: 'donk_bet_river',    isPositional: false, widgets: ['trend_sparkline'] },

// After:
donk_bet_flop:     { displayName: 'Donk Bet Flop',    heroStatsField: 'donk_bet_flop',     isPositional: false, widgets: ['ev_breakdown', 'range_heatmap', 'villain_response', 'trend_sparkline'] },
donk_bet_turn:     { displayName: 'Donk Bet Turn',    heroStatsField: 'donk_bet_turn',     isPositional: false, widgets: ['ev_breakdown', 'by_context', 'trend_sparkline'] },
donk_bet_river:    { displayName: 'Donk Bet River',   heroStatsField: 'donk_bet_river',    isPositional: false, widgets: ['ev_breakdown', 'trend_sparkline'] },
```

#### Aggression Factor (lines 95-97)

```typescript
// Before:
af_flop:           { displayName: 'AF Flop',           heroStatsField: 'af_flop',           isPositional: false, widgets: ['trend_sparkline'] },
af_turn:           { displayName: 'AF Turn',           heroStatsField: 'af_turn',           isPositional: false, widgets: ['trend_sparkline'] },
af_river:          { displayName: 'AF River',          heroStatsField: 'af_river',          isPositional: false, widgets: ['trend_sparkline'] },

// After:
af_flop:           { displayName: 'AF Flop',           heroStatsField: 'af_flop',           isPositional: false, widgets: ['by_context', 'ev_breakdown', 'trend_sparkline'] },
af_turn:           { displayName: 'AF Turn',           heroStatsField: 'af_turn',           isPositional: false, widgets: ['by_context', 'ev_breakdown', 'trend_sparkline'] },
af_river:          { displayName: 'AF River',          heroStatsField: 'af_river',          isPositional: false, widgets: ['by_context', 'ev_breakdown', 'trend_sparkline'] },
```

#### Aggression Frequency (lines 99-101)

```typescript
// Before:
afq_flop:          { displayName: 'Agg Freq Flop',   heroStatsField: 'afq_flop',          isPositional: false, widgets: ['trend_sparkline'] },
afq_turn:          { displayName: 'Agg Freq Turn',   heroStatsField: 'afq_turn',          isPositional: false, widgets: ['trend_sparkline'] },
afq_river:         { displayName: 'Agg Freq River',  heroStatsField: 'afq_river',         isPositional: false, widgets: ['trend_sparkline'] },

// After:
afq_flop:          { displayName: 'Agg Freq Flop',   heroStatsField: 'afq_flop',          isPositional: false, widgets: ['by_context', 'trend_sparkline'] },
afq_turn:          { displayName: 'Agg Freq Turn',   heroStatsField: 'afq_turn',          isPositional: false, widgets: ['by_context', 'trend_sparkline'] },
afq_river:         { displayName: 'Agg Freq River',  heroStatsField: 'afq_river',         isPositional: false, widgets: ['by_context', 'trend_sparkline'] },
```

#### Showdown (lines 104-106)

```typescript
// Before:
went_to_showdown:  { displayName: 'WTSD',             heroStatsField: 'wtsd',              isPositional: false, widgets: ['trend_sparkline'] },
won_at_showdown:   { displayName: 'W$SD',             heroStatsField: 'wsd',               isPositional: false, widgets: ['trend_sparkline'] },
wwsf:              { displayName: 'WWSF',             heroStatsField: 'wwsf',              isPositional: false, widgets: ['trend_sparkline'] },

// After:
went_to_showdown:  { displayName: 'WTSD',             heroStatsField: 'wtsd',              isPositional: false, widgets: ['by_context', 'ev_breakdown', 'trend_sparkline'] },
won_at_showdown:   { displayName: 'W$SD',             heroStatsField: 'wsd',               isPositional: false, widgets: ['by_context', 'ev_breakdown', 'trend_sparkline'] },
wwsf:              { displayName: 'WWSF',             heroStatsField: 'wwsf',              isPositional: false, widgets: ['composition', 'by_context', 'trend_sparkline'] },
```

#### Iso Raise (line 54)

```typescript
// Before:
iso_raise:         { displayName: 'Iso Raise',         heroStatsField: 'iso_raise',         isPositional: false, widgets: ['range_heatmap', 'by_context', 'sizing_histogram', 'ev_breakdown', 'trend_sparkline'] },

// After:
iso_raise:         { displayName: 'Iso Raise',         heroStatsField: 'iso_raise',         isPositional: false, widgets: ['fold_equity', 'ev_breakdown', 'by_context', 'trend_sparkline'] },
```

---

## 2. Backend: `stat_registry.py` Config Additions

### File to modify

- `backend/app/stat_registry.py`

Every widget the frontend references must have a corresponding backend config entry. Below are all missing configs that must be added.

### 2.1 EV_BREAKDOWN_CONFIG additions

Add these entries to the `EV_BREAKDOWN_CONFIG` dict:

```python
# ── Steal section ──
"steal": [
    ("Fold-through", "hp.steal_attempted = TRUE AND hp.saw_flop IS NOT TRUE"),
    ("Called", "hp.steal_attempted = TRUE AND hp.saw_flop = TRUE AND hp.fold_to_3bet IS NULL"),
    ("3-Bet faced", "hp.steal_attempted = TRUE AND hp.fold_to_3bet IS NOT NULL"),
],
"call_steal": [
    ("Won", "hp.call_steal = TRUE AND hp.won_bb > 0"),
    ("Lost", "hp.call_steal = TRUE AND hp.won_bb <= 0"),
],
"three_bet_vs_steal": [
    ("Fold-through", "hp.three_bet_vs_steal = TRUE AND hp.saw_flop IS NOT TRUE"),
    ("Called", "hp.three_bet_vs_steal = TRUE AND hp.saw_flop = TRUE"),
    ("4-Bet faced", "hp.three_bet_vs_steal = TRUE AND hp.fold_to_4bet IS NOT NULL"),
],
"fold_to_steal": [
    ("Fold", "hp.fold_to_steal = TRUE"),
    ("Defend", "hp.faced_steal = TRUE AND hp.fold_to_steal IS NOT TRUE"),
],

# ── Postflop: C-Bet ──
"cbet_flop": [
    ("C-bet flop", "hp.cbet_flop = TRUE"),
    ("Check flop", "hp.cbet_flop_opp = TRUE AND hp.missed_cbet_flop = TRUE"),
],
"cbet_turn": [
    ("C-bet turn", "hp.cbet_turn = TRUE"),
    ("Check turn", "hp.cbet_turn_opp = TRUE AND hp.cbet_turn IS NOT TRUE"),
],
"cbet_river": [
    ("C-bet river", "hp.cbet_river = TRUE"),
    ("Check river", "hp.cbet_river_opp = TRUE AND hp.cbet_river IS NOT TRUE"),
],

# ── Postflop: Fold to C-Bet ──
"fold_to_cbet_flop": [
    ("Fold", "hp.fold_to_cbet_flop = TRUE"),
    ("Call", "hp.fold_to_cbet_flop = FALSE AND hp.raise_cbet_flop IS NOT TRUE"),
    ("Raise", "hp.raise_cbet_flop = TRUE"),
],
"fold_to_cbet_turn": [
    ("Fold", "hp.fold_to_cbet_turn = TRUE"),
    ("Call", "hp.fold_to_cbet_turn = FALSE AND hp.turn_raises = 0"),
    ("Raise", "hp.fold_to_cbet_turn IS NOT NULL AND hp.turn_raises > 0"),
],
"fold_to_cbet_river": [
    ("Fold", "hp.fold_to_cbet_river = TRUE"),
    ("Call", "hp.fold_to_cbet_river = FALSE AND hp.river_raises = 0"),
    ("Raise", "hp.fold_to_cbet_river IS NOT NULL AND hp.river_raises > 0"),
],

# ── Donk Bet ──
"donk_bet_flop": [
    ("Donk bet", "hp.donk_bet_flop = TRUE"),
    ("Check", "hp.donk_bet_flop_opp = TRUE AND hp.donk_bet_flop IS NOT TRUE"),
],
"donk_bet_turn": [
    ("Donk bet", "hp.donk_bet_turn = TRUE"),
    ("Check", "hp.donk_bet_turn_opp = TRUE AND hp.donk_bet_turn IS NOT TRUE"),
],
"donk_bet_river": [
    ("Donk bet", "hp.donk_bet_river = TRUE"),
    ("Check", "hp.donk_bet_river_opp = TRUE AND hp.donk_bet_river IS NOT TRUE"),
],

# ── Showdown ──
"went_to_showdown": [
    ("Won at SD", "hp.won_at_showdown = TRUE"),
    ("Lost at SD", "hp.went_to_showdown = TRUE AND hp.won_at_showdown IS NOT TRUE"),
],
"won_at_showdown": [
    ("Won at SD", "hp.won_at_showdown = TRUE"),
],
"wwsf": [
    ("Won", "hp.won_bb > 0 AND hp.saw_flop = TRUE"),
    ("Lost", "hp.won_bb <= 0 AND hp.saw_flop = TRUE"),
],

# ── Aggression Factor ──
"af_flop": [
    ("Bet/Raise", "hp.saw_flop = TRUE AND (hp.flop_bets + hp.flop_raises) > 0"),
    ("Call/Check/Fold", "hp.saw_flop = TRUE AND (hp.flop_bets + hp.flop_raises) = 0"),
],
"af_turn": [
    ("Bet/Raise", "hp.saw_turn = TRUE AND (hp.turn_bets + hp.turn_raises) > 0"),
    ("Call/Check/Fold", "hp.saw_turn = TRUE AND (hp.turn_bets + hp.turn_raises) = 0"),
],
"af_river": [
    ("Bet/Raise", "hp.saw_river = TRUE AND (hp.river_bets + hp.river_raises) > 0"),
    ("Call/Check/Fold", "hp.saw_river = TRUE AND (hp.river_bets + hp.river_raises) = 0"),
],
```

### 2.2 BY_CONTEXT_CONFIG additions

Add these entries to the `BY_CONTEXT_CONFIG` dict:

```python
# ── Steal section ──
"steal": {
    "dimension": "position",
    "action_sql": "hp.steal_attempted = TRUE",
    "opp_sql": "hp.steal_opp = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
"fold_to_steal": {
    "dimension": "stealer_position",
    "action_sql": "hp.fold_to_steal = TRUE",
    "opp_sql": "hp.faced_steal = TRUE",
    "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.steal_attempted = TRUE AND v.player_id != hp.player_id",
    "group_expr": "v.position",
},
"call_steal": {
    "dimension": "stealer_position",
    "action_sql": "hp.call_steal = TRUE",
    "opp_sql": "hp.faced_steal = TRUE",
    "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.steal_attempted = TRUE AND v.player_id != hp.player_id",
    "group_expr": "v.position",
},
"three_bet_vs_steal": {
    "dimension": "hero_position",
    "action_sql": "hp.three_bet_vs_steal = TRUE",
    "opp_sql": "hp.faced_steal = TRUE",
    "join": "",
    "group_expr": "hp.position",
},

# ── Postflop: C-Bet ──
"cbet_flop": {
    "dimension": "pot_type",
    "action_sql": "hp.cbet_flop = TRUE",
    "opp_sql": "hp.cbet_flop_opp = TRUE",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single-Raised' END",
},

# ── Postflop: Fold to C-Bet ──
"fold_to_cbet_flop": {
    "dimension": "pot_type",
    "action_sql": "hp.fold_to_cbet_flop = TRUE",
    "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single-Raised' END",
},

# ── Showdown ──
"went_to_showdown": {
    "dimension": "pot_type",
    "action_sql": "hp.went_to_showdown = TRUE",
    "opp_sql": "hp.saw_flop = TRUE",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single-Raised' END",
},
"won_at_showdown": {
    "dimension": "pot_type",
    "action_sql": "hp.won_at_showdown = TRUE",
    "opp_sql": "hp.went_to_showdown = TRUE",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single-Raised' END",
},
"wwsf": {
    "dimension": "pot_type",
    "action_sql": "hp.won = TRUE",
    "opp_sql": "hp.saw_flop = TRUE",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single-Raised' END",
},

# ── Donk Bet ──
"donk_bet_turn": {
    "dimension": "position",
    "action_sql": "hp.donk_bet_turn = TRUE",
    "opp_sql": "hp.donk_bet_turn_opp = TRUE",
    "join": "",
    "group_expr": "hp.position",
},

# ── Aggression Factor ──
"af_flop": {
    "dimension": "position",
    "action_sql": "(hp.flop_bets + hp.flop_raises) > 0",
    "opp_sql": "hp.saw_flop = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
"af_turn": {
    "dimension": "position",
    "action_sql": "(hp.turn_bets + hp.turn_raises) > 0",
    "opp_sql": "hp.saw_turn = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
"af_river": {
    "dimension": "position",
    "action_sql": "(hp.river_bets + hp.river_raises) > 0",
    "opp_sql": "hp.saw_river = TRUE",
    "join": "",
    "group_expr": "hp.position",
},

# ── Aggression Frequency ──
"afq_flop": {
    "dimension": "position",
    "action_sql": "(hp.flop_bets + hp.flop_raises) > 0",
    "opp_sql": "hp.saw_flop = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
"afq_turn": {
    "dimension": "position",
    "action_sql": "(hp.turn_bets + hp.turn_raises) > 0",
    "opp_sql": "hp.saw_turn = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
"afq_river": {
    "dimension": "position",
    "action_sql": "(hp.river_bets + hp.river_raises) > 0",
    "opp_sql": "hp.saw_river = TRUE",
    "join": "",
    "group_expr": "hp.position",
},
```

### 2.3 FOLD_EQUITY_CONFIG additions

Add these entries to the `FOLD_EQUITY_CONFIG` dict:

```python
"steal": "hp.steal_attempted = TRUE",
"three_bet_vs_steal": "hp.three_bet_vs_steal = TRUE",
"cbet_river": "hp.cbet_river = TRUE",
"iso_raise": "hp.iso_raise = TRUE",
```

### 2.4 POSTFLOP_BRIDGE_CONFIG additions

Add these entries to the `POSTFLOP_BRIDGE_CONFIG` dict:

```python
"steal": "hp.steal_attempted = TRUE AND hp.saw_flop = TRUE",
"call_steal": "hp.call_steal = TRUE AND hp.saw_flop = TRUE",
```

### 2.5 SIZING_CONFIG additions

Add these entries to the `SIZING_CONFIG` dict. Note: the sizing endpoint currently hardcodes `a.street = 'preflop'`. For postflop c-bet sizing, the street filter must match the stat's street. This requires a small extension to `SIZING_CONFIG` to include the street.

**Option A (minimal, reuse existing pattern):** Change the tuple to include street:

```python
# Current format: (flag_filter, action_type_filter)
# New format: (flag_filter, action_type_filter, street)
# Existing entries get "preflop" as third element for backward compat

"cbet_flop": ("hp.cbet_flop = TRUE", "a.action_type = 'bet'", "flop"),
"cbet_turn": ("hp.cbet_turn = TRUE", "a.action_type = 'bet'", "turn"),
"cbet_river": ("hp.cbet_river = TRUE", "a.action_type = 'bet'", "river"),
```

**This requires a small change to the sizing endpoint** (`backend/app/api/stats.py`, `get_sizing` function) to read the street from the config tuple:

```python
# Before:
flag_filter, action_filter = config

# After:
if len(config) == 3:
    flag_filter, action_filter, street = config
else:
    flag_filter, action_filter = config
    street = "preflop"

# And replace the hardcoded 'preflop' in the query:
# Before: AND a.street = 'preflop'
# After:  AND a.street = '{street}'
```

### 2.6 RESPONSE_DECOMPOSITION additions

The `cbet_flop` stat needs a RESPONSE_DECOMPOSITION entry so the `response_distribution` widget works. Note: `fold_to_cbet_turn` and `fold_to_cbet_river` already exist (lines 360-368).

```python
"cbet_flop": {
    "opp_sql": "hp.cbet_flop = TRUE",
    "fold_sql": "hp.cbet_flop = TRUE AND hp.saw_turn IS NOT TRUE",
    "raise_sql": "hp.cbet_flop = TRUE AND hp.flop_raises > 0",
},
```

This decomposes c-bet outcomes: fold-through (opponent folded to cbet, hero did not see turn), got raised, or got called (remainder).

### 2.7 COMPOSITION_CONFIG addition

```python
"wwsf": [
    ("Showdown win", "hp.won_at_showdown = TRUE"),
    ("Non-showdown win", "hp.won = TRUE AND hp.saw_flop = TRUE AND hp.went_to_showdown IS NOT TRUE"),
    ("Showdown loss", "hp.went_to_showdown = TRUE AND hp.won_at_showdown IS NOT TRUE"),
    ("Non-showdown loss", "hp.won IS NOT TRUE AND hp.saw_flop = TRUE AND hp.went_to_showdown IS NOT TRUE"),
],
```

---

## 3. Summary of Backend Config Counts

| Config Dict | Existing Entries | New Entries | Stats Added |
|-------------|-----------------|-------------|-------------|
| `EV_BREAKDOWN_CONFIG` | 21 | 18 | steal, call_steal, three_bet_vs_steal, fold_to_steal, cbet_flop/turn/river, fold_to_cbet_flop/turn/river, donk_bet_flop/turn/river, went_to_showdown, won_at_showdown, wwsf, af_flop/turn/river |
| `BY_CONTEXT_CONFIG` | 12 | 15 | steal, fold_to_steal, call_steal, three_bet_vs_steal, cbet_flop, fold_to_cbet_flop, went_to_showdown, won_at_showdown, wwsf, donk_bet_turn, af_flop/turn/river, afq_flop/turn/river |
| `FOLD_EQUITY_CONFIG` | 5 | 4 | steal, three_bet_vs_steal, cbet_river, iso_raise |
| `POSTFLOP_BRIDGE_CONFIG` | 1 | 2 | steal, call_steal |
| `SIZING_CONFIG` | 2 | 3 | cbet_flop, cbet_turn, cbet_river |
| `RESPONSE_DECOMPOSITION` | 12 | 1 | cbet_flop |
| `COMPOSITION_CONFIG` | 2 | 1 | wwsf |

---

## 4. Test Checklist

### Automated tests

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all 11 tests pass (no parser/stat_flags changes)
2. `cd frontend && npm run lint` -- no lint errors

### Manual verification (start `make dev`, open Stats page)

For each stat below, click the stat cell to open the detail panel and verify the listed widgets render without errors. Widgets may show `--` or empty states if sample size is low, but should not show errors or 404s.

#### Steal section

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `steal` | range_heatmap, fold_equity, ev_breakdown, villain_response, postflop_bridge, trend | Fold equity shows steal fold-through %. EV breakdown shows Fold-through/Called/3-Bet faced scenarios. Postflop bridge shows c-bet rate in steal pots. |
| `fold_to_steal` | response_dist, range_heatmap, by_context, ev_breakdown, trend | By-context shows breakdown by stealer position (BTN/SB). Response dist shows fold/call/3bet split. |
| `call_steal` | range_heatmap, ev_breakdown, postflop_bridge, by_context, trend | EV breakdown shows Won/Lost. Postflop bridge shows c-bet rate when calling steals. |
| `three_bet_vs_steal` | range_heatmap, fold_equity, ev_breakdown, by_context, trend | Fold equity shows 3bet-vs-steal fold-through %. By-context shows hero position breakdown. |

#### Postflop: C-Bet

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `cbet_flop` | response_dist, ev_breakdown, sizing_histogram, by_context, positional_bar, trend | Sizing shows bet size distribution in BB. By-context shows SRP vs 3BP split. Response dist shows fold/call/raise from villain. |
| `cbet_turn` | ev_breakdown, sizing_histogram, positional_bar, trend | EV breakdown shows c-bet turn vs check turn. |
| `cbet_river` | fold_equity, ev_breakdown, sizing_histogram, positional_bar, trend | Fold equity shows river c-bet fold-through rate. |

#### Postflop: Fold to C-Bet

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `fold_to_cbet_flop` | response_dist, ev_breakdown, by_context, positional_bar, trend | By-context shows pot type breakdown (SRP vs 3BP). |
| `fold_to_cbet_turn` | response_dist, ev_breakdown, positional_bar, trend | Response dist already worked; verify EV breakdown shows fold/call/raise EV. |
| `fold_to_cbet_river` | response_dist, ev_breakdown, positional_bar, trend | Same pattern as turn. |

#### Showdown

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `went_to_showdown` | by_context, ev_breakdown, trend | By-context shows pot type. EV breakdown shows Won at SD / Lost at SD. |
| `won_at_showdown` | by_context, ev_breakdown, trend | Similar to WTSD but from the winning side. |
| `wwsf` | composition, by_context, trend | Composition shows SD win / NSD win / SD loss / NSD loss breakdown. |

#### Donk Bet

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `donk_bet_flop` | ev_breakdown, range_heatmap, villain_response, trend | EV shows donk vs check. Range heatmap shows which hands hero donks. |
| `donk_bet_turn` | ev_breakdown, by_context, trend | By-context shows position breakdown. |
| `donk_bet_river` | ev_breakdown, trend | Minimal widget set, just EV. |

#### Aggression

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `af_flop` | by_context, ev_breakdown, trend | By-context shows position breakdown. |
| `af_turn` | by_context, ev_breakdown, trend | Same pattern. |
| `af_river` | by_context, ev_breakdown, trend | Same pattern. |
| `afq_flop` | by_context, trend | By-context shows position breakdown. No EV breakdown. |
| `afq_turn` | by_context, trend | Same. |
| `afq_river` | by_context, trend | Same. |

#### Iso Raise

| Stat | Widgets to verify | What to look for |
|------|-------------------|------------------|
| `iso_raise` | fold_equity, ev_breakdown, by_context, trend | Fold equity replaces range_heatmap and sizing. Verify no 404 on fold_equity endpoint. |

### API smoke tests

Verify these endpoints return 200 (not 404) for newly configured stats:

```bash
# EV Breakdown
curl -s localhost:8000/api/stats/detail/steal/ev-breakdown | jq .stat_key
curl -s localhost:8000/api/stats/detail/cbet_flop/ev-breakdown | jq .stat_key
curl -s localhost:8000/api/stats/detail/went_to_showdown/ev-breakdown | jq .stat_key
curl -s localhost:8000/api/stats/detail/donk_bet_flop/ev-breakdown | jq .stat_key
curl -s localhost:8000/api/stats/detail/af_flop/ev-breakdown | jq .stat_key

# By Context
curl -s localhost:8000/api/stats/detail/steal/by-context | jq .dimension
curl -s localhost:8000/api/stats/detail/cbet_flop/by-context | jq .dimension
curl -s localhost:8000/api/stats/detail/went_to_showdown/by-context | jq .dimension
curl -s localhost:8000/api/stats/detail/afq_flop/by-context | jq .dimension

# Fold Equity
curl -s localhost:8000/api/stats/detail/steal/fold-equity | jq .fold_pct
curl -s localhost:8000/api/stats/detail/cbet_river/fold-equity | jq .fold_pct
curl -s localhost:8000/api/stats/detail/iso_raise/fold-equity | jq .fold_pct

# Postflop Bridge
curl -s localhost:8000/api/stats/detail/steal/postflop-bridge | jq .cbet_pct
curl -s localhost:8000/api/stats/detail/call_steal/postflop-bridge | jq .cbet_pct

# Sizing (requires street fix)
curl -s localhost:8000/api/stats/detail/cbet_flop/sizing | jq .total
curl -s localhost:8000/api/stats/detail/cbet_turn/sizing | jq .total

# Response Decomposition (analysis endpoint)
curl -s localhost:8000/api/stats/detail/cbet_flop/analysis | jq .response_distribution

# Composition
curl -s localhost:8000/api/stats/detail/wwsf/composition | jq .total
```

### Regression checks

- Verify unchanged stats still render correctly: `vpip`, `pfr`, `open_raise`, `three_bet`, `fold_to_3bet`, `bb_defense`
- Verify the sizing endpoint still works for `open_raise` and `iso_raise` (existing configs)
- Verify `response_distribution` widgets on `fold_to_cbet_turn` and `fold_to_cbet_river` still work (already had RESPONSE_DECOMPOSITION entries)
