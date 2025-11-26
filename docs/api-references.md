# bet-bot API References

**Document:** Centralized API documentation links, endpoints, authentication, and rate limits
**Last Updated:** 2025-11-26
**Audience:** Developers implementing data fetchers and integrations

---

## Quick Links

| API | Status | Documentation | Type |
|-----|--------|---------------|------|
| **API-Football** | Primary | https://www.api-football.com/ | REST API |
| **OpenAI** | Primary | https://platform.openai.com/docs/api-reference | REST API |
| **ESPN** | Fallback | https://www.espn.com/soccer/ | Web Scraping |
| **FlashScore** | Fallback | https://www.flashscore.com/football/ | Web Scraping |
| **Odds-API** | Optional | https://the-odds-api.com/ | REST API |

---

## 1. API-Football (Primary Data Source)

### Documentation
- **Official Docs:** https://www.api-football.com/
- **API Base URL:** https://api-football-v3.p.rapidapi.com/v3/
- **Status Page:** https://www.api-football.com/status

### Authentication
- **Type:** API Key (Header-based)
- **Header:** `x-rapidapi-key`
- **Secondary Header:** `x-rapidapi-host: api-football-v1.p.rapidapi.com`
- **Requirement:** Must be obtained from RapidAPI
- **Key Location:** `Config.API_FOOTBALL_KEY` (environment variable)

### Rate Limits
- **Limit:** 300 requests per minute
- **Header:** `x-ratelimit-requests-remaining` (in response)
- **Rate Limit Response:** HTTP 429 with `Retry-After` header
- **Client-Side Limit:** Implemented as 100 req/min (safety margin)
- **Plan:** ~$15/month (paid tier)

### Endpoints Used

#### Fixtures (Match Data)
```
GET /v3/fixtures
Parameters:
  - date: YYYY-MM-DD (required for today's matches)
  - league: league_id (optional, filter by league)
  - season: YYYY (optional, current season)

Response:
  {
    "fixture": {"id": int, "date": ISO8601},
    "league": {"id": int, "name": str, "country": str, "season": int},
    "teams": {
      "home": {"id": int, "name": str},
      "away": {"id": int, "name": str}
    },
    "venue": {"id": int, "name": str, "city": str}
  }
```

#### Team Statistics (Form Data)
```
GET /v3/teams/statistics
Parameters:
  - team: team_id (required)
  - season: YYYY (required)
  - league: league_id (required)

Response:
  {
    "team": {"id": int, "name": str},
    "statistics": [
      {
        "form": "WWDLW",
        "fixtures": {
          "played": {"home": int, "away": int},
          "wins": {"home": int, "away": int},
          "draws": int,
          "losses": {"home": int, "away": int}
        },
        "goals": {
          "for": {"total": int, "average": float},
          "against": {"total": int, "average": float}
        }
      }
    ]
  }
```

#### Injuries (Player Availability)
```
GET /v3/injuries
Parameters:
  - team: team_id (required)
  - season: YYYY (optional)
  - league: league_id (optional)

Response:
  {
    "player": {
      "id": int,
      "name": str,
      "photo": str
    },
    "team": {"id": int, "name": str},
    "fixture": {"id": int},
    "player_position": str,
    "injury": {"type": str, "reason": str},
    "date": ISO8601,
    "games": {"appearences": int, "lineups": int, "minutes": int}
  }
```

#### Odds (Betting Markets)
```
GET /v3/odds
Parameters:
  - fixture: fixture_id (required)
  - bookmaker: bookmaker_id (optional, filter by bookmaker)

Response:
  {
    "fixture": {"id": int},
    "update": ISO8601,
    "bookmakers": [
      {
        "id": int,
        "name": str,
        "bets": [
          {
            "id": int,
            "name": str,  // "Match Winner", "Goals Over/Under", etc.
            "values": [
              {
                "value": str,  // "Home", "Draw", "Away"
                "odd": float
              }
            ]
          }
        ]
      }
    ]
  }
```

### Data Freshness Requirements
- **Fixtures:** Real-time (must be today)
- **Form:** < 24 hours old
- **Injuries:** < 12 hours old
- **Odds:** < 1 hour old (CRITICAL - reject if stale)

### Implementation Notes
- Response structure uses nested objects (e.g., `fixture.id`, `teams.home.name`)
- Manual field mapping required in fetcher functions
- Timestamps returned in ISO 8601 format with timezone
- Supports pagination via `page` parameter (not used in bet-bot currently)

### Error Codes
| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad request | Check parameters, don't retry |
| 401/403 | Authentication failed | Raise APIAuthenticationError |
| 404 | Resource not found | Return None (graceful degradation) |
| 429 | Rate limit exceeded | Respect Retry-After, retry with backoff |
| 5xx | Server error | Retry with exponential backoff (max 5x) |

### Backup Sources for This API
- ESPN (form, H2H)
- FlashScore (odds, line movement)

**Implementation File:** `src/bet_bot/data/fetchers/api_football.py`

---

## 2. OpenAI (AI Analysis)

### Documentation
- **Official Docs:** https://platform.openai.com/docs/api-reference
- **API Endpoint:** https://api.openai.com/v1/chat/completions
- **Python SDK:** https://github.com/openai/openai-python
- **Pricing:** https://openai.com/pricing/

### Authentication
- **Type:** API Key (Bearer Token)
- **Header:** `Authorization: Bearer {API_KEY}`
- **Requirement:** OpenAI API key from https://platform.openai.com/account/api-keys
- **Key Location:** `Config.OPENAI_API_KEY` (environment variable)

### Rate Limits
- **Free Tier:** Limited (consult OpenAI dashboard)
- **Paid Tier:** Depends on plan (typically 3,500 RPM for GPT-4)
- **Current Model:** gpt-4 (or gpt-4o for cost optimization)
- **Token Limits:** 8,000-128,000 depending on model

### API Usage

#### Chat Completions
```
POST /v1/chat/completions

Request:
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "You are a football betting analyst..."
    },
    {
      "role": "user",
      "content": "Analyze this fixture: [JSON fixture data]"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 500
}

Response:
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": timestamp,
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": int,
    "completion_tokens": int,
    "total_tokens": int
  },
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

### Implementation Notes
- Use official OpenAI Python SDK (already installed)
- Structured JSON input with fixture data
- Response parsing extracts probability estimates and reasoning
- Token usage tracking important for cost monitoring
- Consider batch processing for multiple fixtures

### Cost Optimization
- **Current:** gpt-4 (most accurate, higher cost)
- **Alternative:** gpt-4o or gpt-3.5-turbo (faster, cheaper)
- **Strategy:** Start with GPT-4, migrate to GPT-4o if cost becomes issue

### Error Codes
| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse response |
| 400 | Invalid request | Check prompt format, don't retry |
| 401/403 | Authentication failed | Raise APIAuthenticationError |
| 429 | Rate limit exceeded | Respect Retry-After, retry with backoff |
| 500/502/503 | Server error | Retry with exponential backoff |

**Implementation File:** `src/bet_bot/analysis/ai/client.py` (future)

---

## 3. ESPN (Fallback Data Source)

### Documentation
- **Website:** https://www.espn.com/soccer/
- **Target URLs:**
  - Fixtures: `https://www.espn.com/soccer/schedule`
  - Team Form: `https://www.espn.com/soccer/team/form`
  - Head-to-Head: `https://www.espn.com/soccer/history`

### Authentication
- **Type:** None (public website)
- **Rate Limiting:** Implicit (avoid aggressive scraping)
- **User-Agent:** Required (identify as bot)

### Scraping Strategy
- **HTML Parser:** BeautifulSoup4
- **Target Elements:** `<table class="Table">`
- **Extraction:** Match results, form data, historical records
- **Fragility:** Medium (ESPN redesigns occasionally)

### Data Sources

#### Form Data
- **Path:** Team pages > Recent Results
- **Fields:** Date, Opponent, Result (W/D/L), Goals
- **Freshness:** Daily updates
- **Fallback For:** API-Football form data (if API fails or stale)

#### Head-to-Head
- **Path:** Fixture details > H2H History
- **Fields:** Date, Home team, Away team, Score, Result
- **Freshness:** Static (historical)
- **Fallback For:** API-Football H2H (if API missing data)

### Implementation Notes
- Requires proper HTML parsing and DOM navigation
- CSS class names subject to change (maintenance required)
- No API contract - scraping agreement implicit
- Best effort basis (don't expect 100% reliability)
- Implement robust error handling and validation

### Rate Limiting Courtesy
- Add delays between requests (1-2 seconds)
- Respect `robots.txt` (though ESPN likely has sports data)
- Don't overload with concurrent requests
- Implement proper User-Agent header

**Implementation File:** `src/bet_bot/data/fetchers/espn_scraper.py`

---

## 4. FlashScore (Fallback Data Source)

### Documentation
- **Website:** https://www.flashscore.com/football/
- **Target URLs:**
  - Odds: `https://www.flashscore.com/match/.../#/odds-comparison`
  - Live Scores: `https://www.flashscore.com/match/.../`

### Authentication
- **Type:** None (public website)
- **Rate Limiting:** Implicit (avoid aggressive scraping)
- **User-Agent:** Required

### Scraping Strategy
- **HTML Parser:** BeautifulSoup4 (or Selenium if JavaScript required)
- **Target Elements:** Odds tables, betting comparison sections
- **Extraction:** Odds from multiple bookmakers, line movement
- **Fragility:** High (dynamic content, frequent changes)

### Data Sources

#### Odds Data
- **Path:** Fixture > Odds/Comparison tab
- **Fields:** Bookmaker names, odds by market (1X2, O/U, etc.)
- **Freshness:** Real-time (updates frequently)
- **Fallback For:** API-Football odds (if API fails or stale)

#### Line Movement
- **Path:** Fixture > Odds/Comparison > Historical view
- **Fields:** Opening odds vs. current odds
- **Freshness:** Real-time
- **Use Case:** Detect line movement (optional future feature)

### Implementation Notes
- Odds data may require JavaScript rendering (consider Selenium)
- Site structure changes frequently - requires maintenance
- Multiple bookmakers aggregated (more redundancy)
- Betting odds are highly time-sensitive

### Rate Limiting Courtesy
- Add delays between requests (2-3 seconds)
- Implement Cloudflare/JavaScript detection handling
- Don't attempt rapid concurrent requests
- Implement user-agent rotation if heavily used

**Implementation File:** `src/bet_bot/data/fetchers/flashscore_scraper.py`

---

## 5. Odds-API (Optional Backup)

### Documentation
- **Official Docs:** https://the-odds-api.com/
- **API Base URL:** https://api.the-odds-api.com/v4/
- **Dashboard:** https://the-odds-api.com/dashboard

### Authentication
- **Type:** API Key (Query parameter or header)
- **Parameter:** `apiKey` (in query string)
- **Requirement:** Free or paid API key from The Odds API
- **Key Location:** `Config.ODDS_API_KEY` (environment variable, optional)

### Rate Limits
- **Free Tier:** 500 requests per month
- **Paid Tier:** Up to 100,000 requests per month (~$10/month)
- **Current Plan:** Optional (not required for MVP)

### API Usage

#### Odds Endpoint
```
GET /v4/sports/{sport}/odds
Parameters:
  - apiKey: your-api-key
  - markets: h2h,spreads,totals (comma-separated)
  - regions: uk,eu,us (comma-separated)
  - oddsFormat: decimal or american

Response:
  {
    "data": [
      {
        "id": "fixture_id",
        "sport_key": "soccer_epl",
        "sport_title": "English Premier League",
        "commence_time": ISO8601,
        "home_team": "Team A",
        "away_team": "Team B",
        "bookmakers": [
          {
            "key": "betfair",
            "title": "Betfair",
            "last_update": ISO8601,
            "markets": [
              {
                "key": "h2h",
                "outcomes": [
                  {"name": "Team A", "price": 2.1},
                  {"name": "Draw", "price": 3.5},
                  {"name": "Team B", "price": 3.0}
                ]
              }
            ]
          }
        ]
      }
    ]
  }
```

### Supported Sports
- **Soccer:** `soccer_epl`, `soccer_germany_bundesliga`, etc.
- **Full List:** See documentation at https://the-odds-api.com/sports-odds-data/sports-apis

### Implementation Notes
- Aggregates odds from multiple regional bookmakers
- More comprehensive than single API but adds complexity
- Good as backup if primary source fails
- Requires authentication (API key in request)
- Provides historical data retention

### Error Codes
| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad request | Check parameters |
| 401/403 | Authentication failed | Raise APIAuthenticationError |
| 429 | Rate limit exceeded | Respect Retry-After |
| 5xx | Server error | Retry with backoff |

**Current Status:** Optional (not required for MVP)
**Implementation File:** `src/bet_bot/data/fetchers/odds_api.py` (future)

---

## Integration Architecture

### Data Fetching Flow

```
┌─────────────────────────────────────────┐
│ User: analyze --bankroll 1000           │
└────────────┬────────────────────────────┘
             │
    ┌────────▼─────────┐
    │ Fetch Fixtures   │
    │ (API-Football)   │ ◄─── Primary source
    └────────┬─────────┘
             │
    ┌────────┼─────────────────────┐
    │        │                     │
    ▼        ▼                     ▼
  Form   Injuries               Odds
 API-F  API-F                  API-F
  │      │                       │
  └──┬──┘                        │
     │ Fallback to ESPN          │ Fallback to FlashScore
     │                           │ or Odds-API
     │                           │
     ▼                           ▼
  Consolidation Layer
  (normalize + merge)
     │
     ▼
  OpenAI Analysis
  (probability estimation)
     │
     ▼
  Edge Detection
  (EV calculation)
     │
     ▼
  Display Results
```

### Primary → Fallback Strategy

| Data Type | Primary | Fallback 1 | Fallback 2 |
|-----------|---------|-----------|-----------|
| Fixtures | API-Football | None | N/A |
| Form | API-Football | ESPN | None |
| Injuries | API-Football | None | N/A |
| Odds | API-Football | FlashScore | Odds-API |
| H2H | API-Football | ESPN | None |

### Error Handling Philosophy
- **Continue on non-critical failures** (graceful degradation)
- **Only stop on critical failures** (no fixtures found)
- **Log all failures** for visibility
- **Confidence scoring** reflects data quality

---

## Authentication Setup Guide

### 1. API-Football (Required)

**Get API Key:**
1. Visit https://www.api-football.com/
2. Sign up for free/paid tier
3. Get API key from RapidAPI
4. Add to `.env` file:
   ```bash
   API_FOOTBALL_KEY=your-key-here
   ```

**Verify:**
```bash
python -c "from bet_bot.config import Config; print(Config.API_FOOTBALL_KEY[:8] + '...')"
```

### 2. OpenAI (Required)

**Get API Key:**
1. Visit https://platform.openai.com/account/api-keys
2. Create new API key
3. Add to `.env` file:
   ```bash
   OPENAI_API_KEY=sk-...
   ```

**Verify:**
```bash
python -c "import openai; openai.api_key = open('.env').read().split('=')[1]; print('✓')"
```

### 3. Odds-API (Optional)

**Get API Key:**
1. Visit https://the-odds-api.com/dashboard
2. Sign up for free tier (500 req/month) or paid
3. Add to `.env` file:
   ```bash
   ODDS_API_KEY=your-key-here
   ```

---

## Rate Limiting Strategy

### Per-API Limits

| API | Limit | Client Limit | Implementation |
|-----|-------|--------------|-----------------|
| API-Football | 300 req/min | 100 req/min | RateLimiter class (token bucket) |
| OpenAI | Plan-dependent | 500 req/min | tenacity retry decorator |
| ESPN | Implicit | 1 req/2s | Delay between requests |
| FlashScore | Implicit | 1 req/2s | Delay between requests |
| Odds-API | 500-100k/month | 100 req/min | RateLimiter class |

### Implementation
- **API-Football:** `src/bet_bot/data/fetchers/api_football.py:RateLimiter`
- **OpenAI:** tenacity decorator with exponential backoff
- **Web Scrapers:** `asyncio.sleep()` between requests
- **Global:** Monitor total request rate across all sources

---

## Troubleshooting

### API-Football Issues

**"Authentication failed (401)"**
- Check API key in `.env` is correct
- Verify key hasn't expired
- Ensure `x-rapidapi-host` header matches

**"Rate limit exceeded (429)"**
- Check client-side rate limiter is active
- Verify `Retry-After` header is respected
- Consider reducing concurrent requests

**"No fixtures found (404)"**
- Verify date parameter is correct (YYYY-MM-DD)
- Check league exists and has fixtures today
- Normal response for off-season dates

### OpenAI Issues

**"Invalid API key"**
- Verify key starts with `sk-`
- Check key hasn't been revoked
- Confirm key is in correct environment

**"Timeout (60s+)"**
- OpenAI may be overloaded
- Retry with exponential backoff
- Consider increasing timeout to 120s

### Web Scraper Issues

**"HTML parsing failed"**
- ESPN/FlashScore may have redesigned
- Update CSS selectors and element paths
- Verify HTML structure with `requests.get()` + browser inspect

**"Cloudflare challenge"**
- FlashScore protected by Cloudflare
- Consider Selenium with headless browser
- Add 3-5s delays between requests

---

## References & Documentation

### Official Documentation
- API-Football: https://www.api-football.com/documentation
- OpenAI: https://platform.openai.com/docs/
- The Odds API: https://the-odds-api.com/docs/

### Internal Documentation
- [Technical Specification](docs/technical-spec.md) - System architecture overview
- [Data Dictionary](docs/data-dictionary.md) - Complete field specifications
- [Development Stories](docs/development-stories.md) - Implementation tasks
- [CLAUDE.md](CLAUDE.md) - Mandatory development patterns

### Implementation Files
- API Fetchers: `src/bet_bot/data/fetchers/`
- Configuration: `src/bet_bot/config.py`
- Exception Handling: `src/bet_bot/exceptions.py`
- Models: `src/bet_bot/models/`

---

_This document serves as the single source of truth for all external API integrations. Update this file when APIs change or new integrations are added._
