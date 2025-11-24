# Product Brief: bet-bot

**Date:** 2025-11-24
**Author:** Jephtah
**Context:** Personal Technical Project

---

## Executive Summary

**bet-bot** is a terminal-based **positive expected value (EV) detection tool** for football betting. It combines real-time sports data (fixtures, results, team form, odds) from external APIs with OpenAI's analytical capabilities to identify market inefficiencies where bookmaker odds undervalue true probabilities.

The tool operates on a **disciplined, data-driven approach**: only recommending bets when estimated edge exceeds a conservative threshold (5%+ expected value), and returning "no picks available" when the market is efficient. This mirrors professional betting strategies that prioritize long-term profit through selective, high-value opportunities rather than chasing every game.

Built for developers who bet, bet-bot provides:
- **Transparency**: See the data, odds, and AI reasoning behind every recommendation
- **Discipline**: Automated edge detection removes emotional betting decisions
- **Education**: Learn what creates betting value through AI-explained analysis
- **Efficiency**: Automates time-consuming research across fixtures and bookmakers

**Core philosophy:** Treat betting as a probabilistic investment strategy. Accept variance, embrace selective opportunity detection, and profit through consistent edge identification—not the illusion of certainty. Success comes through disciplined bankroll management and long-term EV accumulation, not individual game predictions.

### Key Design Decisions

**Analysis Approach:** Batch analysis (not real-time)
- Analyze fixtures asynchronously, not during match windows
- Reduces API costs dramatically
- Reduces latency pressure (no need for millisecond responses)
- Shifts strategy to less time-sensitive opportunities

**Market Focus:** Smaller, less-efficient leagues
- Avoid hyper-efficient major leagues (PL, Champions League)
- Target regional leagues, lower divisions, less-watched competitions
- Smaller markets have fewer sharp bettors; inefficiencies persist longer
- Data is still available but less well-analyzed

**Technical Approach:** Work with current APIs, accept some technical debt
- Use available data sources now; don't over-engineer for future changes
- If APIs change, adapt manually rather than build for hypothetical futures
- Prioritize building the betting logic over infrastructure resilience
- Maintainability is good enough, not perfect

**Profitability:** Unknown (experimental)
- Honest: Can't predict if this will be profitable
- Goal is to build, test, learn
- Success metric: Find reproducible edge over 100+ bets (proving concept works)
- Profitability comes later, if at all

---

## Primary User Profile: The Developer-Bettor

**User:** Jephtah (you)
**Context:** Developer who bets on football with analytical mindset but limited time

### What You Think
- "I'm wasting hours researching when this could be automated"
- "Prediction services are black boxes—I don't trust them without transparency"
- "There's probably a pattern in the data I'm missing"
- "Can I actually maintain discipline and NOT bet when there's no edge?"

### What You Feel
- **Frustrated** by repetitive manual research
- **Skeptical** of opaque prediction services
- **Excited** by the technical challenge of building this
- **Anxious** about losing money on poorly-researched bets
- **Doubtful** whether one losing streak will shake the entire system's credibility

### What You See
- Scattered data sources (team news, odds across 3 bookmakers, Reddit, stats sites)
- Time slipping away while analyzing
- Odds shifting faster than you can decide
- Missed opportunities because your analysis was too slow
- Inconsistent decision quality—sometimes disciplined, sometimes emotional

### What You Say
- *"Why didn't I catch that form trend?"*
- *"I need to be more disciplined about only betting with clear edge"*
- *"That prediction service is just marketing hype"*
- *"I wish I knew WHY the algorithm recommended this"*

### What You Do
- Open multiple browser tabs for research (team news, odds, stats)
- Manually check injury reports and current form
- Compare odds across multiple bookmakers
- Occasionally override your own judgment due to FOMO
- Lack systematic tracking of what worked vs. what didn't

### Your Pains 🔴
1. **Time drain** - research is exhausting and repetitive
2. **Inconsistency** - quality varies bet-to-bet (some well-reasoned, some gut-feel)
3. **Missed opportunities** - analysis is too slow; odds move before you decide
4. **Emotional betting** - FOMO overrides discipline despite good intentions
5. **Lack of trust** - can't validate services that won't show their work
6. **Information scatter** - data fragmented across multiple sources
7. **Decision doubt** - after a loss, questions whether approach works at all
8. **No accountability** - no systematic tracking of outcomes and lessons
9. **Analysis paralysis** - sometimes research so much the decision window closes

### Your Desired Gains 🟢
1. **Automation** - tool handles research so you don't have to
2. **Confidence** - transparent reasoning builds trust in recommendations
3. **Enforced discipline** - "no picks" signals you actually respect
4. **Speed** - real-time analysis that captures opportunities before odds move
5. **Pattern detection** - AI spots trends you'd miss manually
6. **Profitability** - consistent small edges compound to real returns
7. **Learning** - understanding *why* deepens your betting knowledge
8. **Consistency** - same logic every time; no mood-based variance
9. **Data-driven pride** - decisions backed by analysis, not hunches
10. **Technical achievement** - build something cool that solves your real problem
11. **Reduced anxiety** - clear threshold (EV > 5%) removes second-guessing

### Design Implications
This empathy map shapes every design decision:
- **Transparency**: Show estimated probability, odds, edge calculation—not just "BET THIS"
- **Discipline Enforcement**: "No picks available" must be truly non-negotiable
- **Unified Interface**: Terminal consolidates all data—no jumping between sites
- **Consistency**: The tool's value is removing variance from your decision-making
- **Education**: Building it yourself deepens understanding vs. using a black-box service
- **Outcome Tracking**: Historical accuracy and ROI tracking prevent doubt after losses

---

## Core Vision

### Problem Statement

Jephtah bets on football but struggles with inconsistent decision-making caused by fragmented research workflows and opaque betting logic. His analysis quality varies wildly bet-to-bet:

- Some picks are thoroughly researched (team form, injuries, odds comparison, historical context)
- Others are intuition-based, missing critical data
- Still others are abandoned because research takes too long with data scattered across multiple sites

**Root causes:**
1. **Data fragmentation** - Team news, odds, form, historical data live in separate sources with no unified view
2. **Invisible decision-making** - Even when researching thoroughly, he can't trace HOW conclusions were reached or validate whether reasoning was sound
3. **Trust deficit** - Uncertain whether his own analysis is rigorous or just lucky

**Result:** He questions every pick: "Did I research this properly or am I just guessing? How would I even know if my reasoning is sound?" This inconsistency compounds—good bets feel unvalidated, bad bets feel like proof the approach doesn't work.

### Why Existing Solutions Fall Short

Prediction services promise to solve this but consistently fail:

- **Suspected bad/incomplete data**: Services show predictions without revealing what data feeds them. Is the injury report current? Are odds from a major bookmaker or a small one? Unknown.
- **Wrong too many times**: Track record is poor (or unprovable because they don't disclose it). After a few losses, trust erodes completely.
- **No transparency**: "65% win probability" with zero explanation. How was this calculated? What data was used? Why should you trust it?
- **One-way relationship**: You consume predictions passively. Can't validate, can't learn, can't debug why something was wrong.
- **Doesn't solve inconsistency**: Even if a service was accurate, your decision-making is still inconsistent because you don't understand the reasoning. You'll second-guess it.

### Proposed Solution

**bet-bot** is a terminal-based betting analysis tool that consolidates fragmented football data and AI reasoning into a single, transparent interface—enabling consistent, trustworthy betting decisions.

It solves the three core problems:

1. **Data Fragmentation** → **Unified Consolidation**
   - Pulls team data, odds, form, injury reports, historical context from multiple APIs
   - Organizes everything into a single view within the terminal
   - No more jumping between 5 browser tabs
   - Single source of truth for analysis

2. **Opaque Logic** → **Full Transparency**
   - Shows data inputs (team form: A is 60% win in last 5, B is 40%)
   - Shows AI reasoning (OpenAI analyzes this data and estimates 58% true win probability)
   - Shows odds evaluation (odds imply 52% win probability, so +5.8% EV)
   - You can validate every step; you understand WHY the pick was made

3. **Inconsistent Analysis** → **Algorithmic Consistency**
   - Same analysis logic every time (removes mood-based, gut-feel variance)
   - Every fixture evaluated with identical rigor
   - Your intuition doesn't override the process
   - Analysis quality is constant, not dependent on your energy level that day

4. **Trust Deficit** → **Validated Track Record**
   - Recommendation history: every pick logged with reasoning, odds, and outcome
   - You see historical accuracy ("Last 50 picks: 56% win rate, 4.2% avg edge")
   - One loss doesn't destroy credibility because you see long-term pattern
   - Transparency + validation = confidence to follow recommendations

**Result:** bet-bot transforms betting from inconsistent guesswork with blind trust into a systematic, transparent, validated process you actually understand and can confidently follow.

### Key Differentiators

**bet-bot is different because it combines three elements competitors can't match:**

1. **Transparent Automation**
   - Prediction services automate but hide the logic (black box)
   - Manual spreadsheets are transparent but never automated
   - bet-bot does BOTH: fully automated analysis you can see completely
   - Every step is visible: data → AI reasoning → edge calculation → recommendation

2. **AI-Powered But Understandable**
   - Uses OpenAI (powerful pattern detection) but doesn't hide behind it
   - Shows what data fed the AI, what the AI concluded, how odds compare
   - You're not blindly trusting an AI; you're validating it
   - AI amplifies your decision-making, not replaces it

3. **Built for YOU, Not Sold to You**
   - You own the tool, see the code, can modify it
   - Not dependent on a service provider's API, pricing, or continued existence
   - Not betting on someone else's track record; you validate it yourself
   - You learn from building AND from using it (technical + betting education)

**Why this matters:**
- Existing prediction services win on ease but lose on trust (you don't know if they're right)
- Manual analysis wins on understanding but loses on consistency (too slow, mood-dependent)
- bet-bot wins on BOTH: you understand everything AND it runs consistently every time
- You can validate it works, tweak it when needed, and maintain confidence because you built it

---

## Target Users

### Primary Users

{{primary_user_segment}}

{{#if secondary_user_segment}}

### Secondary Users

{{secondary_user_segment}}
{{/if}}

{{#if user_journey}}

### User Journey

{{user_journey}}
{{/if}}

---

## Success Metrics

**bet-bot proves itself through multiple validation layers:**

1. **Quick ROI Test (First 10-20 Picks)**
   - Initial validation: Do recommendations show positive ROI immediately?
   - Success: First N picks average positive return (even if small)
   - Failure: Immediate losses suggest fundamental flaw in edge detection
   - Timeline: Days to 1-2 weeks (quick feedback)

2. **Statistical Significance (50+ Picks)**
   - Real proof: Win rate above 55% on 50+ recommendations
   - Success: Achieve 55%+ accuracy consistently
   - This proves edge detection actually works (not luck)
   - Failure: Win rate stays below 52% (no real edge found)
   - Timeline: 4-8 weeks (sufficient sample size)

3. **Consistent Opportunity Detection (Ongoing)**
   - Usability proof: Find 2-3+ picks per analysis run
   - Success: Analysis regularly surfaces exploitable opportunities
   - Failure: Most runs return "NO PICKS AVAILABLE" (either tools broken or no edges exist)
   - Validates that the tool actually works in practice (not just theoretically)
   - Timeline: Continuous (every analysis run)

4. **Personal Validation & Judgment (Continuous)**
   - Real-world proof: Does using bet-bot feel RIGHT?
   - Do recommendations make sense when you review the reasoning?
   - Can you trust the picks enough to actually place bets?
   - Does it reduce the anxiety of inconsistent decision-making?
   - Failure: You distrust the picks and can't force yourself to follow recommendations

### MVP Success Definition

**bet-bot is ready for Phase 2 (optimization) when:**
- ✓ First 10-20 picks show positive ROI (quick win)
- ✓ 50+ picks achieve 55%+ win rate (statistical proof)
- ✓ Regular opportunity detection (2-3+ picks per run typical)
- ✓ You personally trust the recommendations and follow them

**If any metric fails:**
- Negative ROI → Debug edge detection logic or data quality
- <55% win rate → Data or AI analysis isn't reliable; revisit
- Few picks found → Either threshold too high, data too sparse, or no real edges exist
- Low personal trust → Transparency/reasoning needs improvement

{{#if business_objectives}}

### Business Objectives

{{business_objectives}}
{{/if}}

{{#if key_performance_indicators}}

### Key Performance Indicators

{{key_performance_indicators}}
{{/if}}
{{/if}}

---

## MVP Scope

### Core Features

**MVP is fully automated end-to-end analysis on-demand. User runs bet-bot when they want picks, receives recommendations with transparent reasoning, then manually places bets.**

**Essential MVP Features:**

1. **Multi-Source Data Fetching**
   - Fetch upcoming football fixtures (matches available for betting)
   - Fetch team/player form data (recent results, performance trends, injuries, absences)
   - Fetch current odds from bookmakers
   - Consolidate all data into unified view for analysis
   - Scope: Start with best available APIs; focus on leagues/markets where good data exists

2. **Multi-Market Analysis (Not Just Match Outcomes)**
   - Analyze match result predictions (Team A to win, draw, Team B to win)
   - Also analyze prop markets: Total goals, corners, cards, goal scorers, etc.
   - Any market where an exploitable edge can be found
   - Critical: Edges might exist in corners market (less efficient) even if match result is fairly priced

3. **OpenAI-Powered Analysis**
   - Send consolidated fixture data to OpenAI with analysis prompt
   - Request probability estimates for outcomes (not just match results, but any market)
   - Get back: estimated true probability for the outcome
   - Critical: Show what data fed into this analysis (transparent inputs)

4. **Edge Detection & Calculation**
   - Compare AI's estimated probability vs. odds-implied probability
   - Calculate expected value (EV) for each opportunity
   - Filter for picks where EV > threshold (5% as discussed)
   - Return "NO PICKS AVAILABLE" when no edge meets threshold

5. **Transparent Terminal Display**
   - Show for each recommendation:
     - Fixture details (Team A vs Team B, league, date)
     - Data inputs used (form, injuries, historical data, current odds)
     - AI's reasoning/analysis
     - Estimated probability (AI's estimate)
     - Implied probability (from odds)
     - Expected Value calculation (% edge)
     - Confidence level (high/medium/low)
     - Recommended market (match result? corners? cards?)
     - Recommended odds/stake guidance
   - User can understand and validate every step

6. **Bankroll-Based Stake Sizing**
   - Suggest bet size based on edge and bankroll
   - Calculate recommended stake: "With 5% EV and $1000 bankroll, suggest $25 bet"
   - Helps enforce discipline (don't over-bet)
   - Helps manage risk (scale bets to edge quality)
   - Simple sizing model (Kelly Criterion or fractional Kelly) in MVP

7. **On-Demand Execution**
   - User triggers analysis when desired (not automated/scheduled)
   - Analyzes all available upcoming fixtures in one run
   - Surfaces only picks that meet edge threshold
   - Takes X minutes to complete (batch processing is fine)
   - Returns list of recommendations or "NO PICKS AVAILABLE"

**Not in MVP (Future):**
- Outcome logging / accuracy tracking (you validate manually if desired)
- Multiple odds source comparison (use single best API)
- Automated betting integration (you place bets manually)
- Scheduled/automated analysis (on-demand only)
- Mobile app or web UI (terminal only)
- League-specific optimization (start broad, optimize later)
- Learning from past bets to improve analysis

{{#if out_of_scope}}

### Out of Scope for MVP

{{out_of_scope}}
{{/if}}

{{#if mvp_success_criteria}}

### MVP Success Criteria

{{mvp_success_criteria}}
{{/if}}

{{#if future_vision_features}}

### Future Vision

{{future_vision_features}}
{{/if}}

---

{{#if market_analysis}}

## Market Context

{{market_analysis}}
{{/if}}

{{#if financial_considerations}}

## Financial Considerations

{{financial_considerations}}
{{/if}}

{{#if technical_preferences}}

## Technical Preferences

{{technical_preferences}}
{{/if}}

{{#if organizational_context}}

## Organizational Context

{{organizational_context}}
{{/if}}

## Risks and Assumptions

### Critical Risks & Preventive Measures

**Risk 1: Data Quality Collapse**
- *Impact:* Bad recommendations due to incomplete, delayed, or inaccurate data
- *Contributing Factors:* API gaps (injuries, team news, odds delays), data inconsistencies, API downtime
- *Prevention:* Multiple data providers for redundancy, data freshness validation, backtest against historical outcomes, sanity checks before AI analysis


**Risk 2: User Discipline Breakdown**
- *Impact:* Tool works but you ignore "no picks" signals and lose money chasing emotional bets
- *Contributing Factors:* FOMO overrides discipline, forcing bets against recommendations, overriding safeguards
- *Prevention:* Non-negotiable "no picks" enforcement, betting journal/accountability tracking, clear edge math display, position tracking to prevent overexposure

**Risk 3: Trust Erosion After First Loss**
- *Impact:* Black-box recommendations cause skepticism; single loss feels like complete failure
- *Contributing Factors:* Lack of transparency in reasoning, misunderstanding variance in betting
- *Prevention:* Full transparency (show probability estimates, odds, edge calculation), explain variance and positive EV over volume, historical accuracy tracking, confidence scoring

**Risk 4: Technical Debt & Abandonment**
- *Impact:* APIs break, dependencies become outdated, project dies from maintenance burden
- *Contributing Factors:* No automated tests, poor error handling, undocumented code, fear of updates
- *Prevention:* Automated testing from day one, graceful error handling, API health checks, clear data schema documentation, scheduled maintenance

**Risk 5: Market Evolution & Edge Erosion**
- *Impact:* Bookmakers improve models; exploitable inefficiencies diminish over time
- *Contributing Factors:* Market efficiency increases, sharp bettors already exploit obvious opportunities
- *Prevention:* Monitor edge metrics over time, focus on niche/less-efficient markets, build adaptability, accept that tool value may shift to education/transparency

### Critical Assumptions

1. **External API Reliability**: Assumes data providers maintain consistent APIs and data quality standards
2. **Market Inefficiency**: Assumes bookmaker odds contain exploitable mispricing opportunities (especially true for less-popular leagues and prop bets)
3. **AI Capability**: Assumes OpenAI can effectively analyze sports data to improve probability estimates beyond public information
4. **User Discipline**: Assumes you will follow tool recommendations and honor "no picks available" signals—this is the single largest assumption and hardest to control
5. **Profitable Edge Exists**: Assumes you can find +EV opportunities consistently (not guaranteed, depends on market and data quality)

### Key Success Factors (Inversely, Failure Points)

- **Data Quality**: Must validate before analysis
- **Cost Efficiency**: Economics must make sense (edge > API costs)
- **Speed**: Must analyze fast enough to catch real-time opportunities
- **Transparency**: Must explain reasoning to build trust
- **Discipline**: Must have safeguards against emotional betting override
- **Maintainability**: Must be built to evolve as APIs/markets change

{{#if timeline_constraints}}

## Timeline

{{timeline_constraints}}
{{/if}}

{{#if supporting_materials}}

## Supporting Materials

{{supporting_materials}}
{{/if}}

---

_This Product Brief captures the vision and requirements for {{project_name}}._

_It was created through collaborative discovery and reflects the unique needs of this {{context_type}} project._

{{#if next_workflow}}
_Next: {{next_workflow}} will transform this brief into detailed planning artifacts._
{{else}}
_Next: Use the PRD workflow to create detailed product requirements from this brief._
{{/if}}
