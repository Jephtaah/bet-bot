# bet-bot Requirements Document

**Project:** bet-bot - Positive Expected Value Detection Tool for Football Betting
**Author:** Mary (Analyst)
**Date:** 2025-11-24
**Version:** 1.0

---

## Overview

bet-bot is a CLI-based betting analysis tool that consolidates fragmented football data and AI reasoning into a single interface, enabling consistent, transparent, and disciplined betting decisions.

**Core Value Proposition:**
- Transparent automation (see the data, reasoning, and edge calculation)
- Disciplined edge detection (only recommend bets with 5%+ expected value)
- Same-day match analysis (no waiting, no analysis paralysis)
- Educational feedback (understand WHY each recommendation is made)

---

## User Stories & Acceptance Criteria

### US-1: Fetch and Consolidate Same-Day Fixture Data
**As a** developer-bettor
**I want to** get all available fixtures for today in one place
**So that** I can analyze betting opportunities without jumping between websites

**Acceptance Criteria:**
- [ ] Tool identifies current date/time at runtime
- [ ] Pulls all fixtures from API-Football for matches happening "today" (next 24 hours)
- [ ] If no fixtures exist for today, returns "NO MATCHES TODAY" and exits gracefully
- [ ] Consolidates fixture data (teams, league, kickoff time, current odds)
- [ ] Handles API failures gracefully (logs error, suggests retry)

**Definition of Done:**
- Fixtures displayed in structured format
- No crashes on missing data
- Response time < 30 seconds for typical fixture volume

---

### US-2: Enrich Fixture Data with Team Form and Player Information
**As a** user analyzing a fixture
**I want to** see recent team performance, injuries, and head-to-head history
**So that** OpenAI has rich context to estimate accurate probabilities

**Acceptance Criteria:**
- [ ] Fetch team form (last 5-10 results, win %, average goals, home/away split)
- [ ] Fetch injury/suspension data (key players unavailable)
- [ ] Fetch head-to-head history (past 5 matchups between teams)
- [ ] Data sources: API-Football (primary), ESPN scrape (backup), FlashScore scrape (backup)
- [ ] If primary source fails, gracefully use backup data
- [ ] All data validated for freshness (form: 24h, injuries: <12h, H2H: static)

**Definition of Done:**
- Rich data profile per fixture
- Graceful fallback if any data source unavailable
- Data quality validation prevents stale/invalid inputs

---

### US-3: Fetch Current Odds from Multiple Bookmakers
**As a** bettor
**I want to** see odds from reliable sources for all available markets
**So that** edge calculation is accurate and opportunities aren't missed

**Acceptance Criteria:**
- [ ] Pull odds for all major markets (match result, totals, corners, cards, etc.)
- [ ] Odds must be < 1 hour stale (freshness validation)
- [ ] Support at least one primary bookmaker (API-Football/Odds-API)
- [ ] Show odds clearly in analysis output
- [ ] Handle missing odds gracefully (skip that market for analysis)

**Definition of Done:**
- Current odds available for each fixture/market
- Stale odds rejected
- Error handling for API delays

---

### US-4: Analyze Fixture with OpenAI
**As a** system
**I want to** send consolidated fixture data to OpenAI for probability estimation
**So that** the tool provides AI-powered edge detection

**Acceptance Criteria:**
- [ ] Data structured in JSON format with all relevant fields
- [ ] Send to OpenAI with clear analysis prompt
- [ ] Request probability estimates for all markets (not just match result)
- [ ] OpenAI returns structured response (probabilities + reasoning)
- [ ] Handle OpenAI failures gracefully (log error, skip fixture)
- [ ] Cost optimized (batch calls, don't re-analyze same fixture)

**Definition of Done:**
- OpenAI integration working end-to-end
- Response times < 10 seconds per fixture
- Error handling for API timeouts/failures

---

### US-5: Calculate Expected Value and Detect Edge
**As a** system
**I want to** compare AI probability estimates vs. odds-implied probabilities
**So that** I can identify picks with positive expected value

**Acceptance Criteria:**
- [ ] Calculate implied probability from odds (1/odds)
- [ ] Compare to AI-estimated probability
- [ ] Calculate EV = (AI_prob × odds) - 1
- [ ] Filter for picks with EV > 5% threshold
- [ ] Calculate confidence score (high/medium/low) based on data quality
- [ ] Return "NO PICKS AVAILABLE" when no picks meet threshold

**Definition of Done:**
- Edge calculation mathematically correct
- Confidence scoring transparent and reproducible
- Threshold enforcement non-negotiable

---

### US-6: Display Recommendations with Full Transparency
**As a** bettor
**I want to** see clear, structured output showing each pick with reasoning
**So that** I can validate the recommendation before betting

**Acceptance Criteria:**
- [ ] For each pick, display:
  - Fixture details (teams, league, time)
  - Data inputs used (form, injuries, odds)
  - AI's probability estimate + reasoning
  - Odds-implied probability
  - Edge % calculation
  - Confidence % (0-100)
  - Recommended market (match result, corners, etc.)
  - Suggested stake based on bankroll + EV
- [ ] Terminal output is clean and scannable
- [ ] All numbers match the underlying calculations (verifiable)
- [ ] Handle edge cases (no picks, API errors, missing data)

**Definition of Done:**
- Output is professional, transparent, auditable
- User can trace every recommendation back to source data
- Terminal formatting is consistent and readable

---

### US-7: Enforce Bankroll-Based Stake Sizing
**As a** user with limited bankroll
**I want to** see recommended stake sizes based on edge quality and bankroll
**So that** I manage risk and avoid overbetting

**Acceptance Criteria:**
- [ ] Accept bankroll input (one-time config or per-run)
- [ ] Calculate suggested stake = (bankroll × EV_percentage) with conservative multiplier
- [ ] Stake scales with edge quality (bigger edge = bigger stake, proportionally)
- [ ] Display stake alongside each recommendation
- [ ] Include unit sizing guidance (e.g., "0.5 units" terminology)

**Definition of Done:**
- Stake calculations are mathematically sound
- Users can understand and validate sizing logic
- Protects against overbetting on marginal edges

---

## Success Metrics

### Quick ROI Test (First 10-20 Picks)
- **Goal:** Do recommendations show positive ROI immediately?
- **Success:** First N picks average positive return (even if small)
- **Timeline:** Days to 1-2 weeks

### Statistical Significance (50+ Picks)
- **Goal:** Win rate above 55% on 50+ recommendations
- **Success:** Achieve 55%+ accuracy consistently
- **Timeline:** 4-8 weeks

### Consistent Opportunity Detection
- **Goal:** Find 2-3+ picks per analysis run
- **Success:** Analysis regularly surfaces exploitable opportunities
- **Failure:** Most runs return "NO PICKS AVAILABLE"
- **Timeline:** Continuous (every analysis run)

### Personal Validation & Judgment
- **Goal:** Does using bet-bot feel RIGHT?
- **Success:** You trust the picks enough to actually follow recommendations
- **Failure:** You distrust picks and ignore recommendations

---

## Constraints & Requirements

### Functional Constraints
- **Analysis Scope:** Same-day matches ONLY (next 24 hours from request time)
- **No Match Behavior:** If no matches exist for today, exit gracefully with message
- **Execution Model:** Batch processing, on-demand (user triggers manually)
- **Analysis Speed:** Complete in < 2 minutes for typical fixture volume
- **Edge Threshold:** 5% minimum EV for recommendation
- **Confidence Scoring:** Display as percentage (0-100%) based on data quality

### Data Freshness Requirements
- **Fixtures:** Real-time (must be current for today)
- **Odds:** Maximum 1 hour stale
- **Team Form:** Maximum 24 hours stale
- **Player Data (injuries/suspensions):** Maximum 12 hours stale
- **Head-to-Head History:** Static (no freshness requirement)

### Data Sources
- **Primary:** API-Football (paid tier)
- **Backup:** ESPN (scrape)
- **Backup:** FlashScore (scrape)
- **Odds:** API-Football or Odds-API
- **AI Analysis:** OpenAI (GPT-4 or equivalent)

### Non-Functional Requirements
- **Reliability:** Graceful degradation if any data source fails
- **Error Handling:** Never crash; log errors, continue with available data
- **Transparency:** Every calculation traceable to source data
- **Discipline:** "NO PICKS AVAILABLE" is non-negotiable (threshold enforced)
- **Maintainability:** Code supports API changes without breaking

---

## Out of Scope (MVP)

- Outcome logging / accuracy tracking
- Automated betting integration
- Scheduled/automated analysis
- Mobile app or web UI
- League-specific optimization
- Machine learning from past bets
- Telegram/WhatsApp bot integration (Phase 2)
- Multiple bookmaker odds aggregation
- Real-time analysis during matches

---

## Assumptions

1. **Market Inefficiency:** Bookmaker odds contain exploitable mispricing, especially in smaller leagues
2. **API Reliability:** Data providers maintain consistent APIs and data quality
3. **AI Capability:** OpenAI can effectively analyze sports data to improve probability estimates
4. **User Discipline:** You will follow tool recommendations and honor "no picks" signals
5. **Profitable Edge Exists:** You can find +EV opportunities consistently over 50+ picks

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data quality collapse | Bad recommendations | API validation, data freshness checks, sanity checks before analysis |
| User discipline breakdown | Emotional betting overrides tool | Non-negotiable "no picks" enforcement, clear edge display |
| Trust erosion after first loss | Skepticism of recommendations | Full transparency, confidence scoring, historical tracking |
| Technical debt accumulation | System abandonment | Automated tests, graceful error handling, API health checks |
| Market edge erosion | Fewer exploitable opportunities | Monitor edge metrics, focus on niche markets, accept declining ROI |

---

_Next: Technical Specification will define the implementation approach._
