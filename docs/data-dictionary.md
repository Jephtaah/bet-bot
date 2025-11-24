# bet-bot Data Dictionary

**Project:** bet-bot - Positive Expected Value Detection Tool for Football Betting
**Author:** Mary (Analyst) + Amelia (Developer)
**Date:** 2025-11-24
**Version:** 1.0

---

## Overview

This document defines every data field collected, stored, and analyzed by bet-bot. It specifies:
- Field name and data type
- Source API/scraper
- Freshness requirement
- Validation rules
- Example values

---

## Section 1: Fixture Data

### Basic Fixture Information

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `fixture_id` | string | API-Football | Real-time | Unique, non-empty | "548821" |
| `fixture_date` | ISO 8601 | API-Football | Real-time | Must be today | "2025-11-24T15:00:00Z" |
| `kickoff_time` | ISO 8601 | API-Football | Real-time | Must be today ±24h | "2025-11-24T15:00:00Z" |
| `league_name` | string | API-Football | Static | Non-empty | "Championship" |
| `league_country` | string | API-Football | Static | Valid country code | "England" |
| `league_season` | integer | API-Football | Static | Current or previous season | 2025 |
| `league_id` | string | API-Football | Static | Unique per league | "39" |
| `home_team_id` | string | API-Football | Static | Non-empty | "123" |
| `home_team_name` | string | API-Football | Static | Non-empty | "Leeds United" |
| `away_team_id` | string | API-Football | Static | Non-empty | "456" |
| `away_team_name` | string | API-Football | Static | Non-empty | "West Brom" |
| `venue_name` | string | API-Football | Static | Non-empty or null | "Elland Road" |
| `venue_city` | string | API-Football | Static | Non-empty or null | "Leeds" |

---

## Section 2: Team Form Data

### Recent Match Results & Performance

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `team_id` | string | API-Football | Static | Non-empty | "123" |
| `team_name` | string | API-Football | Static | Non-empty | "Leeds United" |
| `last_5_results` | array[string] | API-Football + ESPN | < 24h | Array of W/D/L | ["W", "W", "D", "L", "W"] |
| `last_10_results` | array[string] | API-Football + ESPN | < 24h | Array of W/D/L | ["W", "W", "D", "L", "W", "L", "D", "W", "W", "D"] |
| `wins_last_5` | integer | Calculated | < 24h | 0-5 | 3 |
| `draws_last_5` | integer | Calculated | < 24h | 0-5 | 1 |
| `losses_last_5` | integer | Calculated | < 24h | 0-5 | 1 |
| `win_percentage_5` | float | Calculated | < 24h | 0.0-1.0 | 0.60 |
| `win_percentage_10` | float | Calculated | < 24h | 0.0-1.0 | 0.55 |
| `goals_for_avg_5` | float | API-Football + ESPN | < 24h | >= 0 | 1.8 |
| `goals_against_avg_5` | float | API-Football + ESPN | < 24h | >= 0 | 1.2 |
| `goal_differential_5` | float | Calculated | < 24h | Can be negative | 0.6 |
| `goals_for_avg_10` | float | API-Football + ESPN | < 24h | >= 0 | 1.7 |
| `goals_against_avg_10` | float | API-Football + ESPN | < 24h | >= 0 | 1.3 |
| `goal_differential_10` | float | Calculated | < 24h | Can be negative | 0.4 |
| `home_wins_last_5` | integer | API-Football | < 24h | 0-5 (home games only) | 2 |
| `home_goals_for_avg` | float | API-Football | < 24h | >= 0 | 1.9 |
| `home_goals_against_avg` | float | API-Football | < 24h | >= 0 | 1.1 |
| `away_wins_last_5` | integer | API-Football | < 24h | 0-5 (away games only) | 1 |
| `away_goals_for_avg` | float | API-Football | < 24h | >= 0 | 1.7 |
| `away_goals_against_avg` | float | API-Football | < 24h | >= 0 | 1.3 |

---

## Section 3: Injury & Suspension Data

### Key Player Availability

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `player_id` | string | API-Football | < 12h | Non-empty | "5001" |
| `player_name` | string | API-Football | < 12h | Non-empty | "Patrick Bamford" |
| `player_position` | string | API-Football | < 12h | Forward/Midfielder/Defender/Goalkeeper | "Forward" |
| `player_role` | string | API-Football | < 12h | Starter/Bench/Reserve | "Starter" |
| `injury_status` | string | API-Football | < 12h | Doubt/Injured/Suspended/Out | "Doubt" |
| `injury_type` | string | API-Football | < 12h | Muscle/Fracture/Suspension/Other or null | "Muscle" |
| `injury_date` | ISO 8601 | API-Football | < 12h | Valid date or null | "2025-11-22T00:00:00Z" |
| `expected_return` | ISO 8601 | API-Football | < 12h | Valid date or null | "2025-11-28T00:00:00Z" |
| `impact_severity` | string | Calculated | < 12h | Key/Moderate/Minor | "Key" |
| `missing_key_players_count` | integer | Calculated | < 12h | >= 0 | 2 |
| `missing_key_players_list` | array[string] | Calculated | < 12h | Array of names | ["Patrick Bamford", "Luke Ayling"] |

**Impact Severity Logic:**
- Key: Team's best player or primary starter unavailable
- Moderate: Regular starter unavailable
- Minor: Bench player or rotation unavailable

---

## Section 4: Head-to-Head History

### Past Matchup Results

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `h2h_fixture_id` | string | API-Football + ESPN | Static | Non-empty | "548745" |
| `h2h_date` | ISO 8601 | API-Football + ESPN | Static | Valid date | "2024-11-10T15:00:00Z" |
| `h2h_home_team` | string | API-Football + ESPN | Static | Team name | "Leeds United" |
| `h2h_away_team` | string | API-Football + ESPN | Static | Team name | "West Brom" |
| `h2h_home_goals` | integer | API-Football + ESPN | Static | >= 0 | 2 |
| `h2h_away_goals` | integer | API-Football + ESPN | Static | >= 0 | 1 |
| `h2h_result` | string | Calculated | Static | W/D/L (from home perspective) | "W" |
| `h2h_last_5_results` | array[string] | Calculated | Static | Array of W/D/L | ["W", "D", "W", "L", "W"] |
| `h2h_home_wins` | integer | Calculated | Static | 0-5 | 3 |
| `h2h_draws` | integer | Calculated | Static | 0-5 | 1 |
| `h2h_away_wins` | integer | Calculated | Static | 0-5 | 1 |
| `h2h_home_goals_avg` | float | Calculated | Static | >= 0 | 1.8 |
| `h2h_away_goals_avg` | float | Calculated | Static | >= 0 | 1.0 |

**Data Coverage:** Last 5 matchups (or fewer if fewer exist)

---

## Section 5: Odds Data

### Bookmaker Odds for All Markets

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `bookmaker_name` | string | API-Football / Odds-API | < 1h | Non-empty | "Pinnacle" |
| `odds_updated_at` | ISO 8601 | API-Football / Odds-API | < 1h | Valid timestamp | "2025-11-24T14:30:00Z" |
| `odds_age_minutes` | integer | Calculated | < 1h | 0-60 | 15 |

#### Match Result Market
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `match_result_home_win` | float | API-Football | < 1h | >= 1.0 | 2.10 |
| `match_result_draw` | float | API-Football | < 1h | >= 1.0 | 3.50 |
| `match_result_away_win` | float | API-Football | < 1h | >= 1.0 | 3.20 |

#### Total Goals Market
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `total_goals_over_2_5` | float | API-Football | < 1h | >= 1.0 | 1.85 |
| `total_goals_under_2_5` | float | API-Football | < 1h | >= 1.0 | 1.95 |
| `total_goals_over_3_5` | float | API-Football | < 1h | >= 1.0 | 3.20 |
| `total_goals_under_3_5` | float | API-Football | < 1h | >= 1.0 | 1.35 |

#### Corners Market
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `corners_over_9_5` | float | API-Football (if available) | < 1h | >= 1.0 | 1.75 |
| `corners_under_9_5` | float | API-Football (if available) | < 1h | >= 1.0 | 2.05 |

#### Cards Market
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `cards_over_4_5` | float | API-Football (if available) | < 1h | >= 1.0 | 1.90 |
| `cards_under_4_5` | float | API-Football (if available) | < 1h | >= 1.0 | 1.90 |

**Odds Freshness Rule:** If `odds_age_minutes > 60`, mark as STALE and reject from analysis

---

## Section 6: AI Analysis Output

### OpenAI Probability Estimates

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `ai_analysis_timestamp` | ISO 8601 | OpenAI | Real-time | Valid timestamp | "2025-11-24T14:45:00Z" |
| `ai_model` | string | OpenAI | Static | Model identifier | "gpt-4" |
| `ai_input_data_hash` | string | Calculated | Real-time | SHA256 of input | "a1b2c3d4e5f6..." |

#### Match Result Market Analysis
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `ai_match_result_home_prob` | float | OpenAI | Real-time | 0.0-1.0 | 0.58 |
| `ai_match_result_draw_prob` | float | OpenAI | Real-time | 0.0-1.0 | 0.25 |
| `ai_match_result_away_prob` | float | OpenAI | Real-time | 0.0-1.0 | 0.17 |
| `ai_match_result_reasoning` | string | OpenAI | Real-time | Non-empty | "Leeds showing strong home form (60% win rate). West Brom injuries to key defenders weaken away potential..." |

#### Total Goals Analysis
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `ai_total_goals_over_2_5_prob` | float | OpenAI | Real-time | 0.0-1.0 | 0.62 |
| `ai_total_goals_reasoning` | string | OpenAI | Real-time | Non-empty or null | "Both teams average 1.8+ goals. Expected combined total ~3.5..." |

#### Corners Analysis
| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `ai_corners_over_9_5_prob` | float | OpenAI | Real-time | 0.0-1.0 | 0.55 |
| `ai_corners_reasoning` | string | OpenAI | Real-time | Non-empty or null | "Leeds and West Brom both in top 10 for corner frequency..." |

---

## Section 7: Edge Detection & Calculation

### Expected Value & Filtering

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `implied_probability_home` | float | Calculated | < 1h | 0.0-1.0 | 0.476 |
| `implied_probability_draw` | float | Calculated | < 1h | 0.0-1.0 | 0.286 |
| `implied_probability_away` | float | Calculated | < 1h | 0.0-1.0 | 0.313 |
| `ev_home_win` | float | Calculated | Real-time | Can be negative | 0.058 |
| `ev_draw` | float | Calculated | Real-time | Can be negative | -0.036 |
| `ev_away_win` | float | Calculated | Real-time | Can be negative | -0.046 |
| `ev_percentage` | float | Calculated | Real-time | -1.0 to +1.0 | 0.058 |
| `meets_threshold` | boolean | Calculated | Real-time | true if EV > 5% | true |

**EV Calculation:**
```
implied_probability = 1 / odds
ev = (ai_probability * odds) - 1
ev_percentage = ev * 100
```

**Threshold:** EV > 5% (0.05) required for pick recommendation

---

## Section 8: Confidence Scoring

### Data Quality Assessment

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `base_confidence` | integer | Configured | Static | 50-100 | 75 |
| `form_data_freshness_points` | integer | Calculated | Real-time | 0-20 | 15 |
| `injury_data_completeness_points` | integer | Calculated | Real-time | -20-0 | -10 |
| `odds_freshness_points` | integer | Calculated | Real-time | -10-0 | 0 |
| `sample_size_points` | integer | Calculated | Static | -10-0 | -5 |
| `final_confidence` | integer | Calculated | Real-time | 0-100 | 72 |

**Confidence Scoring Rules:**
1. Start at `base_confidence` (75%)
2. Add points for data freshness:
   - Form < 24h old: +15 pts
   - Form 24-48h old: +10 pts
   - Form > 48h old: -5 pts
3. Add points for injury data:
   - All injuries known: +0 pts
   - Some missing: -10 pts
   - All missing: -20 pts
4. Add points for odds freshness:
   - < 30 min old: +0 pts
   - 30-60 min old: -5 pts
   - > 60 min old: -10 pts (trigger rejection)
5. Add points for sample size:
   - 10+ games form: +0 pts
   - 5-9 games: -5 pts
   - < 5 games: -10 pts
6. Clamp final score to [0, 100]

---

## Section 9: Stake Sizing

### Recommended Bet Amounts

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `user_bankroll` | float | User input | Static (per run) | > 0 | 1000.00 |
| `stake_calculation_formula` | string | Configured | Static | Non-empty | "bankroll × (ev_pct × 0.1) × (confidence / 100)" |
| `suggested_stake` | float | Calculated | Real-time | > 0 | 25.00 |
| `stake_in_units` | float | Calculated | Real-time | > 0 | 0.5 |
| `unit_size` | float | Calculated | Static | > 0 | 50.00 |

**Calculation:**
```
suggested_stake = bankroll × (ev_percentage × 0.1) × (confidence / 100)
unit_size = bankroll / 200  # Conservative default
stake_in_units = suggested_stake / unit_size
```

---

## Section 10: Final Pick Output

### What Gets Displayed to User

| Field | Type | Source | Freshness | Validation | Example |
|-------|------|--------|-----------|-----------|---------|
| `pick_fixture_id` | string | Original | Real-time | Non-empty | "548821" |
| `pick_teams` | string | Original | Real-time | "Team A vs Team B" | "Leeds United vs West Brom" |
| `pick_league` | string | Original | Real-time | Non-empty | "Championship" |
| `pick_kickoff_time` | ISO 8601 | Original | Real-time | Valid time | "2025-11-24T15:00:00Z" |
| `pick_market` | string | Calculated | Real-time | Market identifier | "match_result_home" |
| `pick_ai_probability` | float | AI Output | Real-time | 0.0-1.0 formatted | "58%" |
| `pick_odds_implied_probability` | float | Odds | Real-time | 0.0-1.0 formatted | "48%" |
| `pick_ev_percentage` | float | Calculated | Real-time | Formatted +/- % | "+5.8%" |
| `pick_confidence_percentage` | integer | Calculated | Real-time | 0-100 | "72%" |
| `pick_suggested_odds` | float | Odds | Real-time | >= 1.0 | 2.10 |
| `pick_suggested_stake` | float | Calculated | Real-time | > 0 | "$25" |
| `pick_reasoning_summary` | string | AI Output | Real-time | Non-empty | "Strong home form, weak away defense, high corner frequency" |

---

## Data Quality Validation Rules

### Critical Validations (Stop Fixture if Failed)
- [ ] Fixture date is today (not past, not future)
- [ ] Kickoff time is valid ISO 8601
- [ ] Home team and away team are different entities
- [ ] Odds exist for at least one market
- [ ] Odds are positive (>= 1.0)
- [ ] OpenAI returned probabilities for at least one market

### Degradation Validations (Continue, But Lower Confidence)
- [ ] Form data < 24h old (if older, -5 pts confidence)
- [ ] Injury data < 12h old (if older, continue with lower confidence)
- [ ] Odds < 1h old (if older, reject odds but continue with other data)
- [ ] All injuries known (if some missing, -10 pts)
- [ ] Head-to-head data exists (optional, not required)

### Recovery Rules
- If API-Football fails → use ESPN scrape
- If ESPN scrape fails → continue without form backup
- If injury data missing → continue with available data, lower confidence
- If odds stale → use older odds with confidence penalty
- If OpenAI fails on one fixture → skip that fixture, continue with others

---

## Performance Metrics (For Tracking)

### Fields Logged After Bet Resolution (Future Phase)

| Field | Type | Purpose |
|-------|------|---------|
| `pick_id` | string | Unique identifier |
| `fixture_actual_result` | string | W/D/L actual outcome |
| `pick_outcome` | string | WIN/LOSS/VOID |
| `actual_roi` | float | Return on invested stake |
| `prediction_accuracy` | boolean | AI prediction matched outcome |
| `ai_probability_calibration` | float | How close AI prob was to actual result % |

**Stored for analysis:** Track 50+ picks to validate edge detection

---

_This dictionary enables transparent, traceable analysis. Every number in the output can be traced back to a source, calculation, or confidence assessment._
