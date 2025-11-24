# bet-bot UI/Display Specification

**Project:** bet-bot - Positive Expected Value Detection Tool for Football Betting
**Author:** Sally (UX Designer) + Amelia (Developer)
**Date:** 2025-11-24
**Version:** 1.0

---

## Design Philosophy

**Principles:**
- **Transparency first:** Every number traceable to source
- **Clarity over beauty:** Readable > flashy
- **Scannable output:** User sees key decision factors instantly
- **Consistent spacing:** Professional, not cramped
- **Dark terminal friendly:** Works in standard terminal color schemes

**No gradients, no shadows, no animations.** Clarity and function only.

---

## Terminal Color Scheme

**Colors Used:**
- `white` - Primary text
- `cyan` - Headers, section dividers
- `green` - Positive metrics (edge, wins, confidence)
- `yellow` - Warnings (stale data, low confidence)
- `red` - Errors, critical alerts
- `dim white` - Secondary info, timestamps

**Implementation:** Uses `rich` library color codes

---

## Output States

### State 1: Successful Analysis with Picks

**Scenario:** User runs `bet-bot analyze --bankroll 1000` and picks are found

**Output Structure:**
```
════════════════════════════════════════════════════════════════
                    BET-BOT ANALYSIS RESULTS
════════════════════════════════════════════════════════════════

📊 Analysis Date: 2025-11-24
🕐 Analysis Time: 14:45:30 UTC
💰 Your Bankroll: $1,000

────────────────────────────────────────────────────────────────
PICKS FOUND: 3 recommendations | 2 fixtures analyzed
────────────────────────────────────────────────────────────────

🎯 PICK #1: MATCH RESULT
────────────────────────────────────────────────────────────────

📅 Fixture: Leeds United vs West Brom
📍 League: Championship (England)
🕐 Kickoff: 2025-11-24 at 15:00 UTC

─ DATA INPUTS ──────────────────────────────────────────────────

Team Form:
  🏠 Leeds (Home):     W-W-D-L-W  | 60% win rate | 1.8 goals/game
  🚗 West Brom (Away): W-D-L-L-D  | 20% win rate | 1.2 goals/game

Head-to-Head (Last 5):
  Leeds: 3W-1D-1L vs West Brom | 60% win rate in direct matchups

Injuries & Absences:
  🏥 Key Players Out:
     • Leeds: Luke Ayling (Defender) - Suspected return Nov 28
     • West Brom: None reported

Odds Available:
  🎲 Match Result: Leeds 2.10 | Draw 3.50 | West Brom 3.20

─ AI ANALYSIS ──────────────────────────────────────────────────

AI Probability Estimate:
  Leeds to Win: 58% (Based on: Strong home form, away team injuries)

AI Reasoning:
  "Leeds shows excellent home form with 60% recent wins and 1.8 avg
   goals/game. West Brom arriving weakened with defensive absence.
   Historical H2H favors Leeds. However, recent draw vs Fulham suggests
   slight inconsistency. Conservative estimate: 58% Leeds win."

─ EDGE DETECTION ──────────────────────────────────────────────

Implied Probability (from 2.10 odds): 48%
AI Probability Estimate: 58%

Expected Value (EV):
  (58% × 2.10) - 1 = +0.058 = +5.8% EDGE ✓

─ RECOMMENDATION ──────────────────────────────────────────────

✅ RECOMMENDATION: BET Leeds United at 2.10

📈 Confidence: 72% (GOOD)
   ├─ Form data: Fresh (<24h) ✓
   ├─ Injury data: Current (<12h) ✓
   ├─ Sample size: 10+ games ✓
   └─ Odds freshness: 12 minutes old ✓

💸 Stake Recommendation: $25 (0.5 units)
   └─ Formula: $1000 × (5.8% × 0.1) × (72% / 100) = $25

────────────────────────────────────────────────────────────────

🎯 PICK #2: TOTAL GOALS OVER 2.5
────────────────────────────────────────────────────────────────

📅 Fixture: Same (Leeds United vs West Brom)

─ AI ANALYSIS ──────────────────────────────────────────────────

AI Probability Estimate: Over 2.5 goals at 62%

AI Reasoning:
  "Both teams average 1.8+ goals/game. Recent meetings between Leeds
   and West Brom had 3+ goals in 4 of last 5 matches. Championship
   season avg: 2.8 goals/game. Injury to West Brom defender could
   increase Leeds scoring chances."

─ EDGE DETECTION ──────────────────────────────────────────────

Odds Available: Over 2.5 at 1.85

Implied Probability (from 1.85 odds): 54%
AI Probability Estimate: 62%

Expected Value (EV):
  (62% × 1.85) - 1 = +0.047 = +4.7% EDGE ✗ BELOW THRESHOLD

⚠️  SKIPPED: Edge 4.7% is below 5% threshold
   └─ This pick is marginal; not recommended at current odds

────────────────────────────────────────────────────────────────

🎯 PICK #3: CORNERS OVER 9.5
────────────────────────────────────────────────────────────────

📅 Fixture: Brighton vs Luton Town
📍 League: Premier League (England)
🕐 Kickoff: 2025-11-24 at 20:00 UTC

─ AI ANALYSIS ──────────────────────────────────────────────────

AI Probability Estimate: Over 9.5 corners at 58%

AI Reasoning:
  "Both Brighton and Luton in top-10 for corner frequency. Brighton
   averaging 5.2 corners/game (home), Luton 4.1 (away). Total expected
   ~9.3 corners. Brighton's aggressive wing play + Luton's defensive
   pressure creates corner opportunities."

─ EDGE DETECTION ──────────────────────────────────────────────

Odds Available: Over 9.5 at 1.80

Implied Probability (from 1.80 odds): 56%
AI Probability Estimate: 58%

Expected Value (EV):
  (58% × 1.80) - 1 = +0.044 = +4.4% EDGE ✗ BELOW THRESHOLD

⚠️  SKIPPED: Edge 4.4% is below 5% threshold
   └─ Marginal pick; recommend passing at current odds

────────────────────────────────────────────────────────────────

📋 SUMMARY
════════════════════════════════════════════════════════════════

✅ Picks Meeting Threshold (EV > 5%): 1
   └─ Leeds United to Win: +5.8% EV

⏸️  Marginal Picks (2% < EV < 5%): 2 (informational only)

💼 Total Recommended Stake: $25
📊 Expected Long-term ROI: +5.8% per unit bet

────────────────────────────────────────────────────────────────

⚠️  DATA QUALITY NOTES:
   ✓ All form data current (<24h)
   ✓ All injury data current (<12h)
   ✓ Odds freshness: Good (<30 min)
   ✓ OpenAI analysis: Successful

────────────────────────────────────────────────────────────────

🎯 NEXT STEPS:
   1. Review the recommendation above
   2. Validate the logic makes sense to you
   3. Place bet(s) at recommended odds (or better)
   4. Track outcome for your analysis records

════════════════════════════════════════════════════════════════
```

---

### State 2: No Picks Available (No Edge Found)

**Scenario:** User runs analysis but no fixtures meet the 5% EV threshold

**Output:**
```
════════════════════════════════════════════════════════════════
                    BET-BOT ANALYSIS RESULTS
════════════════════════════════════════════════════════════════

📊 Analysis Date: 2025-11-24
🕐 Analysis Time: 14:45:30 UTC
💰 Your Bankroll: $1,000

────────────────────────────────────────────────────────────────
⚫ NO PICKS AVAILABLE
────────────────────────────────────────────────────────────────

📌 No Matches or Edge Threshold Not Met

Analysis Summary:
  • Fixtures analyzed: 8
  • Fixtures with valid data: 8
  • Picks meeting EV threshold: 0

Why no picks?
  This can mean:
  1. Bookmaker odds are efficient (fairly priced)
  2. Data quality insufficient to confirm edge
  3. Edge exists but below current 5% threshold
  4. No matches today

Marginal Opportunities (informational):
  • Match A: +2.3% EV (below threshold)
  • Match B: +1.8% EV (below threshold)

💡 Recommendation:
   When the market is efficient, the best bet is no bet.
   This disciplined approach protects your bankroll.
   Wait for better opportunities with clear edge.

════════════════════════════════════════════════════════════════
```

---

### State 3: No Matches Today

**Scenario:** No fixtures available for analysis

**Output:**
```
════════════════════════════════════════════════════════════════
                    BET-BOT ANALYSIS RESULTS
════════════════════════════════════════════════════════════════

📊 Analysis Date: 2025-11-24
🕐 Analysis Time: 14:45:30 UTC

────────────────────────────────────────────────────────────────
⚪ NO MATCHES TODAY
────────────────────────────────────────────────────────────────

No fixtures found for today (2025-11-24).

Run bet-bot again tomorrow when matches are available.

Checking next available fixtures...
  2025-11-25: 12 matches available
  2025-11-26: 15 matches available

════════════════════════════════════════════════════════════════
```

---

### State 4: API Failure / Error State

**Scenario:** Critical data fetch failure

**Output:**
```
════════════════════════════════════════════════════════════════
                    BET-BOT ANALYSIS ERROR
════════════════════════════════════════════════════════════════

❌ CRITICAL ERROR: Unable to Proceed

API-Football connection failed (timeout after 30s)

Error Details:
  • Service: API-Football fixtures endpoint
  • Time: 2025-11-24 14:45:30 UTC
  • Retry: Automatic retry in 10 seconds...

Troubleshooting:
  ✓ Check your internet connection
  ✓ Verify OPENAI_API_KEY and API_FOOTBALL_KEY in environment
  ✓ Try again in 2-3 minutes

Log: /Users/user1/.bet-bot/logs/2025-11-24.log

════════════════════════════════════════════════════════════════
```

---

### State 5: Partial Failure (Graceful Degradation)

**Scenario:** One data source fails but analysis continues

**Output:**
```
════════════════════════════════════════════════════════════════
                    BET-BOT ANALYSIS RESULTS
════════════════════════════════════════════════════════════════

📊 Analysis Date: 2025-11-24
🕐 Analysis Time: 14:45:30 UTC
💰 Your Bankroll: $1,000

⚠️  DATA QUALITY WARNING
────────────────────────────────────────────────────────────────

ESPN scraper failed (connection timeout)
  ↳ Using API-Football as primary source
  ↳ H2H data unavailable (will lower confidence on affected picks)

Proceeding with available data...

────────────────────────────────────────────────────────────────
PICKS FOUND: 2 recommendations | 5 fixtures analyzed
────────────────────────────────────────────────────────────────

[Picks displayed as normal, with confidence adjustments noted]

════════════════════════════════════════════════════════════════
```

---

## Component Details

### Pick Header Section

```
🎯 PICK #1: MATCH RESULT
────────────────────────────────────────────────────────────────

📅 Fixture: Team A vs Team B
📍 League: Championship (England)
🕐 Kickoff: 2025-11-24 at 15:00 UTC
```

**Format Rules:**
- Bold pick title (PICK #N: MARKET TYPE)
- Emoji icons for quick scanning
- Fixture details always first
- Consistent spacing (top padding + divider)

---

### Data Inputs Section

```
─ DATA INPUTS ──────────────────────────────────────────────────

Team Form:
  🏠 Team A (Home):     W-W-D-L-W  | 60% win rate | 1.8 goals/game
  🚗 Team B (Away):     W-D-L-L-D  | 20% win rate | 1.2 goals/game

Head-to-Head (Last 5):
  Team A: 3W-1D-1L vs Team B | 60% win rate in direct matchups

Injuries & Absences:
  🏥 Key Players Out:
     • Team A: Player Name (Position) - Est. return [Date]
     • Team B: Player Name (Position) - Est. return [Date]

Odds Available:
  🎲 Match Result: Team A 2.10 | Draw 3.50 | Team B 3.20
```

**Format Rules:**
- "DATA INPUTS" header with left-align divider
- Sub-sections for Form, H2H, Injuries, Odds
- Consistent emoji usage for scanability
- Always show home (🏠) vs away (🚗) clearly
- Show results as string (W-W-D-L-W)
- Show percentages and key metrics

---

### AI Analysis Section

```
─ AI ANALYSIS ──────────────────────────────────────────────────

AI Probability Estimate:
  Team A to Win: 58% (Based on: Strong home form, away team injuries)

AI Reasoning:
  "Full explanation from OpenAI, wrapped at 70 characters...
   Second line of reasoning continues naturally...
   Wrapped text stays readable in terminal."
```

**Format Rules:**
- "AI ANALYSIS" header with left-align divider
- Show probability as percentage with brief context
- Full reasoning in quotes, wrapped for readability
- Natural language, not technical jargon

---

### Edge Detection Section

```
─ EDGE DETECTION ──────────────────────────────────────────────

Implied Probability (from 2.10 odds): 48%
AI Probability Estimate: 58%

Expected Value (EV):
  (58% × 2.10) - 1 = +0.058 = +5.8% EDGE ✓
```

**Format Rules:**
- "EDGE DETECTION" header
- Show implied vs estimated probability clearly
- Show full EV calculation (transparent)
- Green checkmark (✓) if meets threshold
- Red X (✗) if below threshold

---

### Recommendation Section

```
─ RECOMMENDATION ──────────────────────────────────────────────

✅ RECOMMENDATION: BET Team A at 2.10

📈 Confidence: 72% (GOOD)
   ├─ Form data: Fresh (<24h) ✓
   ├─ Injury data: Current (<12h) ✓
   ├─ Sample size: 10+ games ✓
   └─ Odds freshness: 12 minutes old ✓

💸 Stake Recommendation: $25 (0.5 units)
   └─ Formula: $1000 × (5.8% × 0.1) × (72% / 100) = $25
```

**Format Rules:**
- Green checkmark (✅) for recommended bets
- Confidence score with "quality assessment"
- Tree-style checklist of confidence factors
- Stake shown in dollars + units
- Full calculation shown (transparent)

---

### Skipped Pick Section (Below Threshold)

```
─ EDGE DETECTION ──────────────────────────────────────────────

Implied Probability (from 1.85 odds): 54%
AI Probability Estimate: 62%

Expected Value (EV):
  (62% × 1.85) - 1 = +0.047 = +4.7% EDGE ✗ BELOW THRESHOLD

⚠️  SKIPPED: Edge 4.7% is below 5% threshold
   └─ This pick is marginal; not recommended at current odds
```

**Format Rules:**
- Red X (✗) for below-threshold picks
- Yellow warning (⚠️) to indicate skip reason
- Explain why it was skipped
- Still show full analysis (informational)

---

### Summary Section

```
📋 SUMMARY
════════════════════════════════════════════════════════════════

✅ Picks Meeting Threshold (EV > 5%): 1
   └─ Team A to Win: +5.8% EV

⏸️  Marginal Picks (2% < EV < 5%): 2 (informational only)

💼 Total Recommended Stake: $25
📊 Expected Long-term ROI: +5.8% per unit bet
```

**Format Rules:**
- Summary always at end
- Count recommendations clearly
- Separate "recommended" from "marginal"
- Show total stake and expected ROI
- Professional presentation (clear finality)

---

### Data Quality Notes Section

```
────────────────────────────────────────────────────────────────

⚠️  DATA QUALITY NOTES:
   ✓ All form data current (<24h)
   ✓ All injury data current (<12h)
   ✓ Odds freshness: Good (<30 min)
   ✓ OpenAI analysis: Successful

────────────────────────────────────────────────────────────────
```

**Format Rules:**
- Include ONLY if there are warnings
- Green checkmarks for good data
- Yellow warnings for marginal data
- Red alerts for critical issues

---

### Next Steps Section

```
────────────────────────────────────────────────────────────────

🎯 NEXT STEPS:
   1. Review the recommendation above
   2. Validate the logic makes sense to you
   3. Place bet(s) at recommended odds (or better)
   4. Track outcome for your analysis records

════════════════════════════════════════════════════════════════
```

**Format Rules:**
- Always include at end
- Numbered list of actions
- Encourage user validation
- Recommend tracking

---

## Typography & Formatting Rules

### Headers
- **Title Header:** `════════════════════════════════════════════════════════════════`
- **Section Header:** `─ SECTION NAME ──────────────────────────────────────────────`
- **Pick Header:** `🎯 PICK #N: MARKET TYPE`
- **Subsection Header:** `Team Form:`, `Odds Available:`, etc.

### Dividers
- **Major:** `════════════════════════════════════════════════════════════════`
- **Minor:** `────────────────────────────────────────────────────────────────`
- **Divider Width:** 64 characters (standard terminal)

### Line Length
- **Maximum:** 70 characters (wrapping)
- **Reasoning text:** Wrapped naturally
- **Tables:** Never exceed 70 chars per line

### Spacing
- **Top padding:** 1 blank line before major sections
- **Bottom padding:** 1 blank line after major sections
- **Between picks:** 2 blank lines
- **No excessive blank lines:** Never > 2 consecutive

### Icons/Emojis (Used Sparingly)
- `📊` - Analysis/data
- `🕐` - Time
- `💰` - Money/bankroll
- `🎯` - Pick/target
- `📅` - Date
- `📍` - Location
- `🏠` - Home team
- `🚗` - Away team
- `🏥` - Injuries
- `🎲` - Odds
- `📈` - Confidence/metrics
- `💸` - Stake/money
- `📋` - Summary
- `✅` - Success/recommended
- `❌` - Error/critical
- `⚠️` - Warning
- `✓` - Check/verified
- `✗` - Not verified/failed
- `⏸️` - Paused/skipped
- `⚫⚪` - Status indicators

---

## Responsive Behavior

### Terminal Width: 80 columns (standard)
- Output optimized for 80-column terminal
- Dividers: 64 characters (leaves margin)
- Text wrapping: 70 character max line length

### Terminal Width: < 80 columns
- Graceful degradation
- Reduce spacing, keep structure
- Content priority: Data > formatting

### Terminal Width: > 120 columns
- No special adjustments
- Maintain fixed widths (readability)
- Don't stretch content

---

## Color Implementation

Use `rich` library color codes:

```python
from rich.console import Console
from rich.style import Style

console = Console()

# Headers
console.print("[cyan bold]═══════════════════════════════[/cyan bold]")

# Pick recommendation
console.print("[green]✅ RECOMMENDATION: BET Team A[/green]")

# Warnings
console.print("[yellow]⚠️  Warning: Stale odds[/yellow]")

# Errors
console.print("[red bold]❌ CRITICAL ERROR[/red bold]")

# Confidence good
console.print("[green]72%[/green]")

# Confidence low
console.print("[yellow]45%[/yellow]")
```

---

## Testing & Validation

### Visual Testing Checklist
- [ ] Output fits 80-column terminal without horizontal scroll
- [ ] All emojis display correctly (test on user's system)
- [ ] No line exceeds 70 characters (except dividers)
- [ ] Spacing between picks is exactly 2 blank lines
- [ ] Sections are clearly delineated with dividers
- [ ] Numbers align properly in calculations
- [ ] Color codes render in expected terminal
- [ ] "NO PICKS" and "ERROR" states display clearly

---

_Next: Developers implement using `rich` library and Pydantic models to ensure consistency._
