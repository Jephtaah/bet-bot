# bet-bot Technical Specification

**Project:** bet-bot - Positive Expected Value Detection Tool for Football Betting
**Author:** Amelia (Developer)
**Date:** 2025-11-24
**Version:** 1.0

---

## Technology Stack

### Language & Runtime
- **Primary Language:** Python 3.10+
- **Rationale:** Superior data handling (Pandas), native OpenAI integration, rapid development, sports data ecosystem

### Core Dependencies
- **Data Handling:** `pandas` (data transformation), `pydantic` (schema validation)
- **Async/Concurrency:** `asyncio` (native), `aiohttp` (async HTTP)
- **API Integration:** `openai` (official OpenAI SDK)
- **Web Scraping:** `requests`, `beautifulsoup4` (ESPN/FlashScore)
- **Terminal UI:** `rich` (beautiful formatting, tables, colors)
- **CLI Framework:** `typer` (simple, type-hinted command handling)
- **Data Validation:** `pydantic` (runtime type checking, field validation)

### Development & Testing
- `pytest` (unit/integration tests)
- `python-dotenv` (environment variable management)
- `ruff` (linting)
- `mypy` (type checking)

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────┐
│ User runs: bet-bot analyze --bankroll 1000              │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │ Data Fetching Phase     │ (Parallel async)
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │ Fixtures (API-Football) │
        │ Form (API-F + ESPN)     │
        │ Injuries (API-F)        │
        │ H2H (ESPN + FS)         │
        │ Odds (API-F + Odds-API) │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────────┐
        │ Data Consolidation Phase    │
        │ (Normalize, validate, merge)│
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ OpenAI Analysis Phase       │
        │ (Probability estimation)    │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ Edge Detection Phase        │
        │ (EV calc, filtering)        │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ Confidence Scoring          │
        │ (Data quality assessment)   │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ Display & Output Phase      │
        │ (Terminal rendering)        │
        └────────────┬────────────────┘
                     │
              [Results or "NO PICKS"]
```

### Module Breakdown

#### 1. **Data Fetching Layer** (`data/fetchers/`)

**Purpose:** Parallel async fetching from multiple APIs/scrapers

**Modules:**
- `api_football.py` - API-Football integration (fixtures, form, injuries, odds)
- `espn_scraper.py` - ESPN scraping (form, head-to-head)
- `flashscore_scraper.py` - FlashScore scraping (odds, line movement)
- `odds_api.py` - Odds-API integration (backup odds source)

**Key Pattern:**
```python
async def fetch_all_data() -> ConsolidatedFixtures:
    tasks = [
        fetch_fixtures(),
        fetch_form_data(),
        fetch_injuries(),
        fetch_odds(),
        fetch_head_to_head()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return consolidate(results)
```

**Error Handling:**
- If API-Football fails → use scrape backup
- If scrape fails → continue with missing data (graceful degradation)
- Log all failures for debugging

#### 2. **Data Consolidation Layer** (`data/consolidation/`)

**Purpose:** Normalize data from multiple sources into unified schema

**Modules:**
- `normalizer.py` - Converts all sources to standard format
- `validator.py` - Validates data freshness and quality
- `merger.py` - Merges overlapping data (API-Football primary, scrapes supplement)

**Key Responsibility:**
- Take messy data from 3+ sources
- Output clean `Fixture[]` with consistent fields
- Flag data quality issues (stale data, gaps)

**Data Quality Rules:**
- Reject odds > 1 hour stale
- Reject injuries > 12 hours stale
- Accept form data up to 24 hours old
- Head-to-head is static (no freshness check)

#### 3. **OpenAI Analysis Layer** (`analysis/ai/`)

**Purpose:** Send structured data to OpenAI, get probability estimates

**Modules:**
- `prompt_builder.py` - Constructs analysis prompt with fixture data
- `client.py` - Manages OpenAI API calls with retry logic
- `response_parser.py` - Parses OpenAI response into structured probabilities

**Prompt Strategy:**
```
Input: JSON with fixture, form, injuries, odds
Output:
{
  "markets": [
    {
      "type": "match_result",
      "probabilities": {"home": 0.58, "draw": 0.25, "away": 0.17},
      "reasoning": "..."
    },
    {
      "type": "total_goals_over_2_5",
      "probability": 0.62,
      "reasoning": "..."
    }
  ]
}
```

**Key Pattern:**
- One OpenAI call per fixture (batch processing)
- Structured JSON input/output
- Fallback for API failures (mark fixture as "analysis failed")

#### 4. **Edge Detection Layer** (`analysis/edge/`)

**Purpose:** Calculate expected value, filter for picks

**Modules:**
- `ev_calculator.py` - EV = (AI_prob × odds) - 1
- `threshold_filter.py` - Filter for EV > 5%
- `confidence_scorer.py` - Assess data quality reliability

**Confidence Scoring Logic:**
```
confidence = base_score(75%)
if data_freshness_excellent: confidence += 15
if data_freshness_good: confidence += 10
if missing_form_data: confidence -= 10
if missing_injury_data: confidence -= 15
if odds_stale_but_valid: confidence -= 5
confidence = clamp(0, 100)
```

#### 5. **Stake Sizing Layer** (`analysis/stakes/`)

**Purpose:** Calculate recommended bet sizes

**Modules:**
- `stake_calculator.py` - Size based on bankroll + EV + confidence

**Formula:**
```
stake = bankroll × (EV_percentage * 0.1) × (confidence / 100)
Example: $1000 bankroll, 5% EV, 80% confidence
  = 1000 × (0.05 * 0.1) × (0.8)
  = 1000 × 0.005 × 0.8 = $4
```

Conservative multiplier (0.1) prevents overexposure

#### 6. **Display Layer** (`display/`)

**Purpose:** Render results to terminal

**Modules:**
- `formatter.py` - Formats picks for terminal display
- `renderer.py` - Uses `rich` for beautiful output
- `error_handler.py` - Displays error states gracefully

**Output Structure:**
```
🎯 MATCH RESULT: Championship | Team A vs Team B | Nov 25, 15:00

📊 ANALYSIS
  Team A Win Probability (AI): 58%
  Implied from Odds (2.10): 48%

💰 EDGE: +5.8% EV
📈 CONFIDENCE: 72%

🎲 RECOMMENDATION: Bet Team A at 2.10
💸 Suggested Stake: $25 (0.5 units)

---
```

#### 7. **Configuration & CLI** (`cli/`, `config/`)

**Purpose:** Handle user input, manage configurations

**Modules:**
- `main.py` - Entry point, Typer CLI setup
- `commands.py` - `analyze` command definition
- `config.py` - Bankroll, API keys, preferences

**CLI Interface:**
```bash
bet-bot analyze --bankroll 1000
# Returns picks or "NO MATCHES TODAY"

bet-bot config set-bankroll 1000
bet-bot config set-api-key OPENAI_API_KEY
```

---

## API Integrations

### 1. API-Football (Primary Data Source)

**Purpose:** Fixtures, team form, injuries, odds

**Endpoints:**
- `GET /fixtures?date={date}&league={league_id}` - Today's fixtures
- `GET /teams/statistics?team={team_id}&season={season}&league={league_id}` - Team form
- `GET /fixtures/{fixture_id}?include=statistics` - Form, odds
- `GET /injuries?team={team_id}` - Current injuries

**Pricing:** ~$15/month (paid tier)

**Rate Limits:** 300 requests/minute (sufficient)

**Data Quality:** Excellent for major leagues, good for smaller leagues

### 2. ESPN (Scraper)

**Purpose:** Backup form data, head-to-head history

**Scraping Strategy:**
- Target URLs: `espn.com/soccer/...`
- Extract: `<table class="Table">` with historical results
- Backup to: If API-Football form is missing or stale

**Fragility:** Medium (ESPN redesigns occasionally, requires maintenance)

**Fallback:** If scrape fails, continue without ESPN data

### 3. FlashScore (Scraper)

**Purpose:** Backup odds, line movement

**Scraping Strategy:**
- Target URLs: `flashscore.com/football/...`
- Extract: Odds tables from key bookmakers
- Use if: API-Football odds unavailable or stale

**Fragility:** Medium (scraping odds is fragile; site structure changes)

**Fallback:** If scrape fails, use primary odds source

### 4. Odds-API (Optional Backup)

**Purpose:** Backup odds aggregation if primary source fails

**Pricing:** ~$10/month (optional)

**Data Quality:** Aggregates from multiple bookmakers

---

## Data Schema

See `data-dictionary.md` for complete field definitions.

**Core Models (Pydantic):**

```python
class Team(BaseModel):
    id: str
    name: str
    form_5_games: list[str]  # ['W', 'W', 'D', 'L', 'W']
    avg_goals_for: float
    avg_goals_against: float
    injuries: list[InjuredPlayer]

class Fixture(BaseModel):
    id: str
    home_team: Team
    away_team: Team
    league: str
    kickoff_time: datetime
    odds: dict[str, dict[str, float]]  # market -> {outcome: odds}
    head_to_head_history: list[PastResult]

class AIAnalysis(BaseModel):
    fixture_id: str
    markets: list[MarketAnalysis]

class MarketAnalysis(BaseModel):
    market_type: str  # 'match_result', 'total_goals', 'corners'
    ai_probability: float
    reasoning: str
    confidence: float  # 0-100

class Pick(BaseModel):
    fixture_id: str
    market: str
    ai_probability: float
    implied_probability: float
    ev_percentage: float
    confidence: float
    recommended_stake: float
    suggested_odds: float
```

---

## Error Handling Strategy

### API Failures
```python
try:
    data = await fetch_api_football_fixtures()
except APIError:
    logger.warning("API-Football down, using ESPN scrape")
    data = await scrape_espn_fixtures()
except ScraperError:
    logger.error("All fixture sources failed")
    sys.exit("Unable to fetch fixtures")
```

### Data Quality Issues
```python
if data.odds_age > timedelta(hours=1):
    logger.warning("Odds stale, lowering confidence")
    confidence -= 10

if data.injuries_missing:
    logger.warning("Injury data missing, skipping fixture")
    continue
```

### OpenAI Failures
```python
try:
    result = await openai.call(fixture_data)
except RateLimitError:
    logger.error("OpenAI rate limit, waiting 60s")
    await asyncio.sleep(60)
    retry()
except APIError:
    logger.error("OpenAI API error, skipping fixture")
    continue
```

---

## Performance & Scaling

### Batch Processing Strategy
- All fixtures analyzed in **single run** (no incremental analysis)
- Parallel fetching using `asyncio.gather()` for data sources
- Sequential OpenAI analysis (respects rate limits)
- Total runtime target: **< 2 minutes** for typical day (20-30 fixtures)

### Optimization
- Async I/O prevents blocking on network calls
- Batch OpenAI calls (1 call per fixture, parallel queuing)
- Cache API responses within single run (don't re-fetch same data)
- Limit to target leagues only (reduce fixture volume)

### Scalability
- Single machine, no distributed processing needed
- Can handle 50+ fixtures per run comfortably
- If > 100 fixtures, consider league filtering

---

## Testing Strategy

### Unit Tests
- EV calculation accuracy
- Confidence scoring logic
- Data normalization (all sources)
- Pydantic model validation

### Integration Tests
- API-Football integration (test fixtures endpoint)
- ESPN scraper (test parsing)
- FlashScore scraper (test parsing)
- OpenAI integration (test with mock response)
- End-to-end: fetch → consolidate → analyze → display

### Test Data
- Fixture JSON from API-Football (save sample)
- Historical HTML from ESPN/FlashScore (save snapshots)
- OpenAI response examples (save fixtures)

### Coverage Target
- Minimum 80% code coverage
- 100% coverage for critical paths (EV calc, edge detection)

---

## Deployment & Runtime

### Development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run analysis
python -m bet_bot.cli analyze --bankroll 1000
```

### Production
- Standalone Python script
- Install via: `pip install -r requirements.txt`
- Run daily as cron job (optional future phase)

### Environment Variables
```
OPENAI_API_KEY=sk-...
API_FOOTBALL_KEY=...
ODDS_API_KEY=... (optional)
LOG_LEVEL=INFO
```

---

## Future Enhancements (Not MVP)

1. **Outcome Tracking:** Log picks + results for accuracy tracking
2. **Telegram Bot:** Wrap CLI in Telegram interface
3. **Historical Backtesting:** Validate edge detection against past seasons
4. **League Optimization:** Learn which leagues have best edges
5. **Advanced Stake Sizing:** Kelly Criterion, Dynamic threshold adjustment
6. **UI Dashboard:** Web-based results history + performance analytics

---

_Next: Data Dictionary will define every field and its source._
