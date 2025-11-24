# bet-bot Development Stories

**Project:** bet-bot - Implementation Roadmap
**Date:** 2025-11-24
**Format:** User Stories for Developer (you)

---

## PHASE 1: Foundation & CLI Setup

### Story 1.1: Initialize Python Project Structure
**As a** developer
**I want to** set up the basic Python project with proper directory structure
**So that** I have a foundation for all subsequent development

**Acceptance Criteria:**
- [ ] Create `bet-bot/` project directory with standard Python layout
- [ ] Set up `/src/bet_bot/` package structure with `__init__.py` files
- [ ] Create `/tests/` directory for unit/integration tests
- [ ] Create `/config/` directory for configuration files
- [ ] Create `.env.template` with required environment variables
- [ ] Create `requirements.txt` with all dependencies listed
- [ ] Create `pytest.ini` for test configuration
- [ ] Create `.gitignore` (Python standard)

**Definition of Done:**
- Project structure matches standard Python conventions
- Can run `python -m pip install -r requirements.txt` without errors
- Can run `pytest` even with no tests yet

---

### Story 1.2: Install & Configure Dependencies
**As a** developer
**I want to** install all required dependencies for the project
**So that** I can start building features immediately

**Acceptance Criteria:**
- [ ] Create virtual environment (`venv`)
- [ ] Install: `typer`, `pydantic`, `aiohttp`, `asyncio`, `pandas`, `rich`, `python-dotenv`
- [ ] Install dev dependencies: `pytest`, `mypy`, `ruff`
- [ ] Generate `requirements.txt` with pinned versions
- [ ] Document Python version requirement (3.10+)
- [ ] All imports work without errors

**Definition of Done:**
- `pip list` shows all required packages installed
- `python -c "import bet_bot"` works
- `pytest --version` works

---

### Story 1.3: Create CLI Entry Point with Typer
**As a** developer
**I want to** create a basic CLI command structure using Typer
**So that** I can build the `bet-bot analyze` command

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/cli/main.py` with Typer app setup
- [ ] Implement basic `bet-bot --help` command
- [ ] Implement stub `bet-bot analyze --help` command
- [ ] Command accepts `--bankroll` argument (required, float)
- [ ] Command accepts optional `--config` argument
- [ ] Running `bet-bot analyze --bankroll 1000` prints "Starting analysis..."
- [ ] Add version flag (`--version`)

**Definition of Done:**
- `python -m bet_bot.cli analyze --bankroll 1000` runs without error
- Help text displays correctly
- Can pass bankroll value and retrieve it inside command

---

### Story 1.4: Set Up Configuration Management
**As a** developer
**I want to** create a configuration system for API keys and settings
**So that** I can manage environment variables securely

**Acceptance Criteria:**
- [ ] Create `Pydantic` config model (`Config` class in `/src/bet_bot/config/`)
- [ ] Load from `.env` file using `python-dotenv`
- [ ] Define required fields: `OPENAI_API_KEY`, `API_FOOTBALL_KEY`
- [ ] Define optional fields: `ODDS_API_KEY`, `LOG_LEVEL`
- [ ] Validate API keys are not empty on startup
- [ ] Raise clear error if required keys missing
- [ ] Store config singleton accessible from anywhere

**Definition of Done:**
- Application reads `.env` file on startup
- Missing required API key causes clear error message
- Config values accessible via `config.openai_api_key`

---

### Story 1.5: Implement Structured Logging
**As a** developer
**I want to** set up logging that captures debug info for troubleshooting
**So that** I can debug API failures and data issues easily

**Acceptance Criteria:**
- [ ] Create logger configuration in `/src/bet_bot/utils/logging.py`
- [ ] Log to console (colored output via `rich`)
- [ ] Log to file: `/var/log/bet-bot/{date}.log` (or user home directory)
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR
- [ ] Include timestamps, log level, module name in each log
- [ ] Respect `LOG_LEVEL` environment variable
- [ ] Never expose API keys in logs

**Definition of Done:**
- Logs appear in console with proper formatting
- Log file created with entries
- Debug logs only appear when `LOG_LEVEL=DEBUG`
- No API keys visible in any log

---

## PHASE 2: Data Fetching Layer

### Story 2.1: Create Pydantic Models for Data Structures
**As a** developer
**I want to** define all data models used throughout the application
**So that** I have type safety and validation for all data

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/models/fixtures.py` with `Fixture`, `Team`, `League` models
- [ ] Create `/src/bet_bot/models/form.py` with `TeamForm`, `RecentResult` models
- [ ] Create `/src/bet_bot/models/injuries.py` with `InjuredPlayer`, `Injury` models
- [ ] Create `/src/bet_bot/models/odds.py` with `Odds`, `Market` models
- [ ] Create `/src/bet_bot/models/analysis.py` with `AIAnalysis`, `MarketAnalysis` models
- [ ] All models use Pydantic with proper validation
- [ ] Models include docstrings explaining fields
- [ ] Add example values to each model

**Definition of Done:**
- All models can be imported without error
- Can create instances with valid data
- Invalid data raises validation errors
- `pytest` can validate model structure

---

### Story 2.2: Integrate API-Football SDK
**As a** developer
**I want to** set up the API-Football client with proper authentication
**So that** I can fetch fixtures, form, and injury data

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/fetchers/api_football.py`
- [ ] Initialize API client with `API_FOOTBALL_KEY` from config
- [ ] Implement `fetch_fixtures(date)` function
- [ ] Implement `fetch_team_form(team_id, league_id)` function
- [ ] Implement `fetch_injuries(team_id)` function
- [ ] Implement `fetch_odds(fixture_id)` function
- [ ] Add retry logic (3 attempts, exponential backoff)
- [ ] Handle rate limiting gracefully
- [ ] Log all API calls (URL, response status, timestamp)

**Definition of Done:**
- Can call each function without errors (with valid API key)
- Responses map to Pydantic models
- Rate limit errors are caught and logged
- API calls include proper error messages

---

### Story 2.3: Implement ESPN Form Data Scraper
**As a** developer
**I want to** scrape ESPN for team form data as a backup source
**So that** I have redundancy if API-Football fails

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/fetchers/espn_scraper.py`
- [ ] Scrape team form from ESPN URLs
- [ ] Extract: last 5-10 results, goals for/against, win percentage
- [ ] Add retry logic (2 attempts with timeout)
- [ ] Handle HTML parsing errors gracefully
- [ ] Log scraping status (success/failure)
- [ ] Never call ESPN scraper unless API-Football fails
- [ ] Response maps to `TeamForm` model

**Definition of Done:**
- Scraper extracts data without crashing
- Can parse sample ESPN pages
- Handles missing elements (graceful degradation)
- Logs clearly when scraping fails

---

### Story 2.4: Fetch Odds from Primary Source
**As a** developer
**I want to** fetch current odds for all available markets
**So that** edge calculation has accurate pricing data

**Acceptance Criteria:**
- [ ] Use API-Football's odds endpoint as primary
- [ ] Fetch: match result, total goals, corners, cards markets
- [ ] Validate odds freshness (timestamp < 1 hour old)
- [ ] Return odds in normalized format (market → outcome → odds)
- [ ] Handle missing markets gracefully (skip, don't fail)
- [ ] Log odds age for each fixture
- [ ] If odds > 1h old, mark as stale but continue

**Definition of Done:**
- Can fetch odds for multiple fixtures
- Stale odds are flagged (not rejected yet)
- Response includes timestamp for validation

---

### Story 2.5: Implement Graceful Degradation for Data Sources
**As a** developer
**I want to** automatically fall back to backup sources if primary fails
**So that** the system continues even when one API/scraper fails

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/fetchers/__init__.py` with `fetch_all_data()` function
- [ ] Try API-Football first for each data type
- [ ] On failure, try ESPN scraper (for form data)
- [ ] On all failures, log warning and continue with missing data
- [ ] Never crash the entire run because of one source failure
- [ ] Track which sources succeeded/failed in output
- [ ] Confidence scoring will penalize missing data later

**Definition of Done:**
- Can handle API-Football timeout → falls back to ESPN
- Can handle ESPN scraper failure → continues without data
- Clear logging shows which sources used
- Analysis continues even with partial data

---

## PHASE 3: Data Consolidation & Validation

### Story 3.1: Create Data Consolidation Pipeline
**As a** developer
**I want to** merge fixture data from multiple sources into unified format
**So that** analysis has consistent, clean data

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/consolidation/consolidator.py`
- [ ] Implement `consolidate_fixtures()` that takes raw fixture list
- [ ] Merge API-Football + ESPN + scrape data into single `Fixture` objects
- [ ] Handle conflicting data (prefer fresher source)
- [ ] Normalize all fields to standard format
- [ ] Return list of `Fixture` objects with complete metadata

**Definition of Done:**
- Consolidator accepts raw data from fetchers
- Outputs clean, consistent `Fixture` list
- No data loss (all sources merged, not replaced)

---

### Story 3.2: Implement Data Freshness Validation
**As a** developer
**I want to** validate that all data meets freshness requirements
**So that** analysis isn't based on stale information

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/consolidation/validator.py`
- [ ] Implement freshness checks:
  - Fixtures: Must be today (±24h from now)
  - Odds: Must be < 1 hour old
  - Form: Must be < 24 hours old
  - Injuries: Must be < 12 hours old
- [ ] Flag violations as CRITICAL or DEGRADATION
- [ ] CRITICAL: Reject fixture entirely
- [ ] DEGRADATION: Accept but lower confidence later
- [ ] Log all validation results per fixture

**Definition of Done:**
- Validator rejects fixtures with stale odds
- Validator accepts fixture but flags missing injury data
- Clear logging shows why each fixture passed/failed validation

---

### Story 3.3: Create Data Quality Scoring
**As a** developer
**I want to** assess overall data quality for each fixture
**So that** confidence scoring can account for data limitations

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/data/consolidation/quality_scorer.py`
- [ ] Score on 0-100 scale based on:
  - All required fields present: +20 pts
  - All data < 24h old: +20 pts
  - Injury data present: +15 pts
  - H2H data present: +10 pts
  - Multiple odds markets available: +10 pts
  - Form data from 10+ games: +10 pts
- [ ] Clamp to [0, 100]
- [ ] Attach quality score to each fixture

**Definition of Done:**
- Each fixture has `data_quality_score` (0-100)
- Score calculation is transparent and reproducible
- Poor quality fixtures are flagged (not rejected)

---

## PHASE 4: AI Analysis Integration

### Story 4.1: Build OpenAI Prompt Builder
**As a** developer
**I want to** create structured prompts for OpenAI analysis
**So that** AI gets rich context to estimate probabilities

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/ai/prompt_builder.py`
- [ ] Build prompt that includes:
  - Fixture details (teams, league, date)
  - Team form (last 5-10 results, goals, win %)
  - Injury/suspension info
  - Head-to-head history
  - Current odds for all markets
- [ ] Format data clearly for AI understanding
- [ ] Request probabilities for: match result, total goals, corners, cards
- [ ] Request reasoning explanation
- [ ] Keep prompt concise (< 2000 tokens)

**Definition of Done:**
- Prompt is human-readable and clear
- Contains all required context
- Requests structured JSON response

---

### Story 4.2: Integrate OpenAI API Client
**As a** developer
**I want to** create an OpenAI client that calls GPT for analysis
**So that** I can get AI probability estimates

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/ai/client.py`
- [ ] Initialize OpenAI client with API key
- [ ] Implement `analyze_fixture(fixture_data)` function
- [ ] Send prompt to GPT-4 (or GPT-3.5 if cost is concern)
- [ ] Parse JSON response into `AIAnalysis` model
- [ ] Add retry logic (2 attempts on failure)
- [ ] Handle rate limiting (queue requests)
- [ ] Log token usage for cost tracking
- [ ] Handle timeout (30s max per fixture)

**Definition of Done:**
- Can call OpenAI and get response
- Response parses to `AIAnalysis` model
- Token usage logged for budget monitoring
- Timeouts handled gracefully

---

### Story 4.3: Create Response Parser for AI Output
**As a** developer
**I want to** parse OpenAI responses into structured data
**So that** edge detection can work with clean probabilities

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/ai/response_parser.py`
- [ ] Parse JSON response from OpenAI
- [ ] Extract probabilities for each market
- [ ] Extract reasoning for each market
- [ ] Validate probabilities are 0.0-1.0 and sum correctly
- [ ] Map to `MarketAnalysis` objects
- [ ] Handle malformed responses gracefully
- [ ] Log parsing errors with raw response for debugging

**Definition of Done:**
- Parser handles valid OpenAI responses
- Parser handles malformed JSON (logs error, continues)
- Probabilities are validated before use

---

### Story 4.4: Batch Analyze All Fixtures with OpenAI
**As a** developer
**I want to** analyze multiple fixtures efficiently with OpenAI
**So that** full analysis completes in < 2 minutes

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/ai/analyzer.py` with `analyze_all_fixtures()` function
- [ ] Send each fixture to OpenAI sequentially (respect rate limits)
- [ ] Process results as they return
- [ ] Skip fixture if OpenAI fails (mark with error, continue)
- [ ] Log progress (X of Y fixtures analyzed)
- [ ] Return list of fixtures with AI analysis attached
- [ ] Total runtime < 2 minutes for 20-30 fixtures

**Definition of Done:**
- Can analyze 20 fixtures in < 2 minutes
- All fixtures have AI analysis or error status
- Progress logging shows which fixtures completed

---

## PHASE 5: Edge Detection & Filtering

### Story 5.1: Implement Expected Value Calculation
**As a** developer
**I want to** calculate EV for each AI probability + odds pair
**So that** I can identify picks with positive edge

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/edge/ev_calculator.py`
- [ ] Implement EV formula: `EV = (AI_prob × odds) - 1`
- [ ] Calculate implied probability: `1 / odds`
- [ ] Calculate for all available markets (match result, totals, corners, etc.)
- [ ] Return EV in both decimal (0.058) and percentage (+5.8%)
- [ ] Handle edge case: odds <= 1.0 (invalid, skip)
- [ ] Handle edge case: AI prob outside [0.0, 1.0] (invalid, skip)

**Definition of Done:**
- EV calculations are mathematically correct
- Can verify against manual calculation
- Handles edge cases without crashing

---

### Story 5.2: Create Threshold Filter for Edge Detection
**As a** developer
**I want to** filter picks that meet the 5% EV threshold
**So that** only high-value recommendations are returned

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/edge/threshold_filter.py`
- [ ] Filter for picks with EV > 5% (0.05)
- [ ] Separate into: RECOMMENDED (EV > 5%), MARGINAL (2% < EV < 5%), LOW (EV < 2%)
- [ ] Return only RECOMMENDED picks in main output
- [ ] Log MARGINAL picks for user reference
- [ ] Return "NO PICKS AVAILABLE" if zero RECOMMENDED picks found
- [ ] Never lower threshold (discipline enforcement)

**Definition of Done:**
- Picks are correctly categorized by EV
- Only threshold-meeting picks in output
- Marginal picks shown for reference but not recommended

---

### Story 5.3: Implement Confidence Scoring Logic
**As a** developer
**I want to** score confidence in each recommendation based on data quality
**So that** user knows reliability of pick

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/edge/confidence_scorer.py`
- [ ] Start with base score: 75%
- [ ] Add points:
  - Form < 24h: +15 pts
  - Form 24-48h: +10 pts
  - Injuries < 12h: +5 pts
  - Odds < 30 min: +5 pts
  - 10+ games form: +0 pts (already counted)
- [ ] Subtract points:
  - Form > 48h: -5 pts
  - Missing injuries: -10 pts
  - Odds 30-60 min: -5 pts
  - Odds > 60 min: -10 pts
  - < 5 games form: -10 pts
- [ ] Clamp to [0, 100]

**Definition of Done:**
- Confidence score calculated for each pick
- Scores reflect data quality realistically
- Score is transparent in output

---

### Story 5.4: Create Edge Detection Pipeline
**As a** developer
**I want to** run full edge detection on all analyzed fixtures
**So that** recommendations are ready for display

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/edge/__init__.py` with `detect_edges()` function
- [ ] Input: List of fixtures with AI analysis
- [ ] Calculate EV for each market
- [ ] Score confidence for each pick
- [ ] Filter by threshold
- [ ] Output: List of `Pick` objects (recommended + marginal)
- [ ] Log: Total picks found, picks above threshold, edge distribution

**Definition of Done:**
- Pipeline accepts analyzed fixtures
- Returns clean list of `Pick` objects
- "NO PICKS" case handled properly

---

## PHASE 6: Stake Sizing

### Story 6.1: Implement Stake Calculator
**As a** developer
**I want to** calculate recommended bet sizes based on edge and bankroll
**So that** user doesn't overbets marginal picks

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/analysis/stakes/stake_calculator.py`
- [ ] Accept: bankroll, EV%, confidence%
- [ ] Formula: `stake = bankroll × (EV_pct × 0.1) × (confidence / 100)`
- [ ] Example: $1000 bankroll, 5% EV, 80% confidence = $4 stake
- [ ] Calculate unit sizing: 1 unit = bankroll / 200
- [ ] Return: suggested_stake ($), stake_in_units (units)
- [ ] Never suggest stake > bankroll (clamp to reasonable %)

**Definition of Done:**
- Stake calculation mathematically correct
- Can verify against manual calculation
- Conservative multiplier (0.1) prevents overexposure

---

## PHASE 7: Display & Output

### Story 7.1: Create Terminal Formatter for Picks
**As a** developer
**I want to** format picks for clean terminal display
**So that** user can understand each recommendation

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/display/formatter.py`
- [ ] Format each pick with:
  - Fixture details (teams, league, time)
  - Data inputs (form, injuries, odds)
  - AI analysis (probability, reasoning)
  - Edge detection (implied vs AI, EV calc)
  - Confidence score breakdown
  - Stake recommendation
- [ ] Use `rich` library for formatting
- [ ] Colors: cyan headers, green recommended, yellow warnings
- [ ] Max line width: 70 characters (wrapping)
- [ ] Dividers: 64 characters wide

**Definition of Done:**
- Formatted output matches UI spec exactly
- Text wraps properly at 70 chars
- Fits in 80-column terminal without scroll

---

### Story 7.2: Implement Results Renderer
**As a** developer
**I want to** render final results to terminal with all states
**So that** user sees professional output

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/display/renderer.py`
- [ ] Render state: "PICKS FOUND" (1+ recommendations)
- [ ] Render state: "NO PICKS AVAILABLE" (0 recommendations)
- [ ] Render state: "NO MATCHES TODAY" (no fixtures)
- [ ] Render state: "ERROR" (critical failure)
- [ ] Render state: "DEGRADED" (partial data failure)
- [ ] Add summary section (count, total stake, expected ROI)
- [ ] Add data quality notes
- [ ] Add next steps

**Definition of Done:**
- All output states render correctly
- Output matches UI spec design
- No crashes on edge cases

---

### Story 7.3: Create Error Display Handler
**As a** developer
**I want to** display errors clearly without crashing
**So that** user understands what went wrong

**Acceptance Criteria:**
- [ ] Create `/src/bet_bot/display/error_handler.py`
- [ ] Format error messages clearly
- [ ] Include: error type, timestamp, suggestion
- [ ] Log full error for debugging
- [ ] Show helpful troubleshooting steps
- [ ] Never expose raw stack traces to user
- [ ] Suggest retry or configuration check

**Definition of Done:**
- Error messages are clear and actionable
- User doesn't see raw Python errors
- Log files contain full debugging info

---

## PHASE 8: Integration & Testing

### Story 8.1: Wire All Layers Together in CLI
**As a** developer
**I want to** connect all layers into the main `analyze` command
**So that** full pipeline runs end-to-end

**Acceptance Criteria:**
- [ ] Import all modules into CLI command
- [ ] Execute in order: fetch → consolidate → analyze → edge → stake → render
- [ ] Pass data between layers without errors
- [ ] Accept bankroll from CLI argument
- [ ] Log execution time for each phase
- [ ] Handle exceptions at top level (don't crash CLI)
- [ ] Return proper exit codes (0 success, 1 error)

**Definition of Done:**
- `bet-bot analyze --bankroll 1000` executes full pipeline
- Timing logged for each phase
- No unhandled exceptions

---

### Story 8.2: Write Unit Tests for Critical Paths
**As a** developer
**I want to** test edge detection and stake sizing logic
**So that** calculations are correct

**Acceptance Criteria:**
- [ ] Create `/tests/unit/test_ev_calculator.py`
- [ ] Test EV calculation: (0.58 × 2.10) - 1 = 0.058
- [ ] Test edge cases: odds=1.0, AI_prob=0, AI_prob=1
- [ ] Create `/tests/unit/test_stake_calculator.py`
- [ ] Test formula: 1000 × (0.05 × 0.1) × (0.8) = 4
- [ ] Create `/tests/unit/test_confidence_scorer.py`
- [ ] Test confidence calculation with various inputs
- [ ] Minimum 80% code coverage for these modules

**Definition of Done:**
- `pytest` runs all tests successfully
- All calculation tests pass
- Coverage report shows > 80%

---

### Story 8.3: Integration Test: Full Pipeline
**As a** developer
**I want to** test the full pipeline with mock data
**So that** I can validate end-to-end flow before real APIs

**Acceptance Criteria:**
- [ ] Create `/tests/integration/test_full_pipeline.py`
- [ ] Mock API-Football responses (save sample JSON)
- [ ] Mock OpenAI responses (save sample JSON)
- [ ] Mock ESPN scraper (save sample HTML)
- [ ] Run full pipeline: fetch → consolidate → analyze → render
- [ ] Verify output contains picks (or "NO PICKS")
- [ ] Verify no crashes on missing optional data

**Definition of Done:**
- Integration test passes with mock data
- Can trace data through all layers
- Output is valid and complete

---

### Story 8.4: Manual Testing with Real Data
**As a** developer
**I want to** test with actual API responses
**So that** I validate everything works end-to-end

**Acceptance Criteria:**
- [ ] Run `bet-bot analyze --bankroll 1000` with real API keys
- [ ] Verify fixtures fetch successfully
- [ ] Verify OpenAI analysis returns probabilities
- [ ] Verify edge detection finds picks (or correctly says "NO PICKS")
- [ ] Verify output displays cleanly in terminal
- [ ] Test with 0 picks (check "NO PICKS" message)
- [ ] Test with 1+ picks (verify formatting)
- [ ] Document any API errors for future debugging

**Definition of Done:**
- Full pipeline runs with real data
- Output is readable and correct
- All features working as designed

---

## PHASE 9: Validation & Refinement

### Story 9.1: Monitor First 10 Picks for Quick ROI Validation
**As a** bettor
**I want to** place first 10-20 picks and track results
**So that** I can validate if edge detection actually works

**Acceptance Criteria:**
- [ ] Create manual tracking sheet (spreadsheet or file)
- [ ] Log each pick: date, fixture, market, odds, stake, result, ROI
- [ ] After 10 picks, calculate:
  - Win rate (%)
  - Average ROI per bet
  - Cumulative P&L
- [ ] Success: Positive ROI on first 10
- [ ] Failure: Negative ROI → Debug edge detection logic

**Definition of Done:**
- 10 picks placed and outcomes tracked
- ROI calculated
- Decision made: continue or debug

---

### Story 9.2: Gather 50+ Picks for Statistical Validation
**As a** bettor
**I want to** accumulate 50+ picks over 4-8 weeks
**So that** I can validate with statistical significance

**Acceptance Criteria:**
- [ ] Continue placing picks from bet-bot recommendations
- [ ] Track all 50+ picks with outcomes
- [ ] Calculate:
  - Win rate (goal: > 55%)
  - Average EV delivered (should match predictions)
  - P&L over 50 picks
- [ ] Analyze:
  - Which markets perform best?
  - Which leagues have better edges?
  - Any systematic issues?
- [ ] Success: 55%+ win rate on 50+ picks
- [ ] Failure: < 55% → Edge detection flawed

**Definition of Done:**
- 50+ picks completed with outcomes
- Statistical analysis done
- Decision made: MVP success or needs debugging

---

### Story 9.3: Document Lessons Learned & Next Phase
**As a** developer
**I want to** document what worked and what needs improvement
**So that** Phase 2 can be planned based on real data

**Acceptance Criteria:**
- [ ] Document: Edge detection accuracy (win rate)
- [ ] Document: Most common pick types/markets
- [ ] Document: API reliability issues (if any)
- [ ] Document: Data quality problems (if any)
- [ ] Document: User trust factors (what made you confident?)
- [ ] Decide: Is system profitable enough to continue?
- [ ] Plan Phase 2 features if MVP successful

**Definition of Done:**
- Lessons document created
- Go/no-go decision made
- Next phase planned (if go)

---

## Summary

**Total Stories: 39**

**Timeline Estimates (rough):**
- Phase 1 (Foundation): 2-3 days
- Phase 2 (Data Fetching): 3-4 days
- Phase 3 (Consolidation): 2 days
- Phase 4 (AI Analysis): 2 days
- Phase 5 (Edge Detection): 2 days
- Phase 6 (Stakes): 1 day
- Phase 7 (Display): 2 days
- Phase 8 (Integration): 2-3 days
- Phase 9 (Validation): 4-8 weeks (real betting)

**Ready to start Phase 1?**
