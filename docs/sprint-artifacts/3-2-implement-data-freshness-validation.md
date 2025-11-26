# Story 3.2: Implement Data Freshness Validation

Status: ready-for-dev

## Story

As a developer,
I want to validate that all data meets freshness requirements,
so that analysis isn't based on stale information.

## Acceptance Criteria

1. Create `/src/bet_bot/data/consolidation/validator.py`
2. Implement freshness checks:
   - Fixtures: Must be today (±24h from now)
   - Odds: Must be < 1 hour old
   - Form: Must be < 24 hours old
   - Injuries: Must be < 12 hours old
3. Flag violations as CRITICAL (reject fixture) or DEGRADATION (accept but lower confidence)
4. Return validation results per fixture with clear status codes
5. Log all validation results at appropriate levels (INFO for pass, WARNING for degradation, ERROR for critical)
6. Create Pydantic model for validation results including reason/explanation
7. Integrate with consolidation pipeline (validator receives consolidated fixtures)
8. Handle edge case: missing timestamps - treat as critical failure
9. Handle edge case: future dates - treat as critical failure
10. Return list of fixtures with validation status attached

## Tasks / Subtasks

- [ ] Task 1: Review data freshness requirements and models (AC: #1, #2, #6)
  - [ ] Load `/src/bet_bot/data/consolidation/consolidator.py` to understand source_lineage structure
  - [ ] Check timestamp fields available on consolidated fixtures (form_updated, injuries_updated, odds_updated, fixture_date)
  - [ ] Review Story 3.1 for source tracking implementation
  - [ ] Document freshness thresholds: odds=1h, form=24h, injuries=12h, fixtures=±24h
  - [ ] Understand validation result categories: PASS, DEGRADATION, CRITICAL

- [ ] Task 2: Create ValidationResult Pydantic model (AC: #6)
  - [ ] Create `ValidationResult` model with fields: fixture_id, status (enum: PASS/DEGRADATION/CRITICAL), reason, data_freshness_score (0-100)
  - [ ] Add timestamp field (when validation occurred)
  - [ ] Add detailed field for each data type: fixture_valid, odds_status, form_status, injuries_status, h2h_status
  - [ ] Include source information (which data type failed, which passed)
  - [ ] Ensure model is serializable (for logging/storage)

- [ ] Task 3: Create validator module structure (AC: #1)
  - [ ] Create `/src/bet_bot/data/consolidation/validator.py`
  - [ ] Export `validate_fixtures()` function from module
  - [ ] Import datetime, timezone for timestamp comparisons
  - [ ] Import logging for validation reporting
  - [ ] Ensure no circular imports with consolidator.py

- [ ] Task 4: Implement fixture date validation (AC: #2, #3)
  - [ ] Function: `_validate_fixture_date(fixture_date)` returns PASS or CRITICAL
  - [ ] Check: fixture_date is today (±24 hours from now)
  - [ ] Handle: missing fixture_date → CRITICAL
  - [ ] Handle: future date > 24h → CRITICAL
  - [ ] Handle: past date > 24h → CRITICAL
  - [ ] Log reason if fails (e.g., "fixture_date is 2025-11-20, expected today 2025-11-27")

- [ ] Task 5: Implement odds freshness validation (AC: #2, #3)
  - [ ] Function: `_validate_odds_freshness(odds_timestamp)` returns PASS or DEGRADATION
  - [ ] Check: odds_timestamp is < 1 hour old
  - [ ] Handle: missing odds_timestamp → CRITICAL (cannot trust odds)
  - [ ] Handle: odds > 1h old → DEGRADATION (accept but flag for lower confidence)
  - [ ] Handle: odds in future → CRITICAL
  - [ ] Log age in minutes if stale (e.g., "odds are 75 minutes old")
  - [ ] Return age_minutes in validation result for confidence scoring later

- [ ] Task 6: Implement form data freshness validation (AC: #2, #3)
  - [ ] Function: `_validate_form_freshness(form_timestamp)` returns PASS or DEGRADATION
  - [ ] Check: form_timestamp is < 24 hours old
  - [ ] Handle: missing form_timestamp → DEGRADATION (accept partial data)
  - [ ] Handle: form > 24h old → DEGRADATION
  - [ ] Handle: form in future → CRITICAL
  - [ ] Log age in hours if stale
  - [ ] Return age_hours in validation result

- [ ] Task 7: Implement injuries freshness validation (AC: #2, #3)
  - [ ] Function: `_validate_injuries_freshness(injuries_timestamp)` returns PASS or DEGRADATION
  - [ ] Check: injuries_timestamp is < 12 hours old
  - [ ] Handle: missing injuries_timestamp → DEGRADATION (accept without injury data)
  - [ ] Handle: injuries > 12h old → DEGRADATION (data may be outdated)
  - [ ] Handle: injuries in future → CRITICAL
  - [ ] Log age in hours if stale
  - [ ] Return age_hours in validation result

- [ ] Task 8: Implement H2H validation (AC: #2, #3)
  - [ ] Function: `_validate_h2h(h2h_data)` returns PASS or DEGRADATION
  - [ ] Note: H2H is static data (no freshness check needed)
  - [ ] Check: h2h exists (is not None or empty list)
  - [ ] Handle: missing h2h → DEGRADATION (accept without h2h)
  - [ ] Return status (h2h presence for confidence scoring)

- [ ] Task 9: Implement overall fixture validation orchestration (AC: #1, #4, #10)
  - [ ] Function: `async def validate_fixtures(consolidated_fixtures: list[Fixture]) -> list[Fixture]`
  - [ ] For each fixture:
    - [ ] Call fixture_date validation (CRITICAL failure means skip fixture)
    - [ ] Call odds freshness validation
    - [ ] Call form freshness validation
    - [ ] Call injuries freshness validation
    - [ ] Call h2h validation
    - [ ] Aggregate results into ValidationResult
  - [ ] Attach validation_result to fixture object (add field or store separately)
  - [ ] Return all fixtures (both passing and flagged) with validation attached

- [ ] Task 10: Implement validation status aggregation (AC: #3, #4)
  - [ ] Determine overall fixture status based on component validations:
    - [ ] CRITICAL from any component → overall CRITICAL (reject fixture)
    - [ ] DEGRADATION from one+ components → overall DEGRADATION (accept but flag)
    - [ ] PASS from all → overall PASS
  - [ ] Log fixture validation summary (e.g., "Fixture 12345: DEGRADATION - odds 65m old, form 20h old")
  - [ ] Reason field should explain which data points are problematic

- [ ] Task 11: Implement logging and reporting (AC: #5, #10)
  - [ ] For each PASS fixture: Log at INFO level "Fixture {fixture_id} validation passed"
  - [ ] For each DEGRADATION fixture: Log at WARNING level "Fixture {fixture_id} has data quality issues: {reason}"
  - [ ] For each CRITICAL fixture: Log at ERROR level "Fixture {fixture_id} validation failed, will be rejected: {reason}"
  - [ ] At end: Log summary "Validated X fixtures: Y passed, Z degraded, W critical"
  - [ ] Never crash on validation failure (all fixtures processed)

- [ ] Task 12: Implement edge case handling (AC: #8, #9)
  - [ ] Handle: timestamp is None/null → treat as critical failure
  - [ ] Handle: timestamp is in future (> now) → treat as critical failure
  - [ ] Handle: timestamp is very old (e.g., 10 years ago) → treat as critical failure
  - [ ] Handle: timezone issues (naive vs aware datetime) → normalize and compare safely
  - [ ] Handle: fixture_date comparison across UTC boundaries → use datetime.now(timezone.utc)

- [ ] Task 13: Create validation integration function (AC: #7)
  - [ ] Implement `validate_and_filter()` function that:
    - [ ] Accepts consolidated fixtures from Story 3.1
    - [ ] Validates all fixtures
    - [ ] Optionally filters (return only PASS, or include DEGRADATION)
    - [ ] Returns validated fixture list with results attached
  - [ ] Document which downstream stages (3.3 quality scoring, 4.x analysis) can accept DEGRADATION vs must reject CRITICAL

- [ ] Task 14: Write comprehensive unit tests (AC: #2, #4, #5, #10)
  - [ ] Create `/tests/unit/test_validator.py`
  - [ ] Test fixture date validation:
    - [ ] Fresh fixture (today) → PASS
    - [ ] Old fixture (1 day old) → PASS (within ±24h)
    - [ ] Very old fixture (2 days old) → CRITICAL
    - [ ] Future fixture (1 day future) → PASS
    - [ ] Far future fixture (2 days future) → CRITICAL
    - [ ] Missing fixture_date → CRITICAL
  - [ ] Test odds freshness:
    - [ ] Fresh odds (10 min old) → PASS
    - [ ] Stale odds (90 min old) → DEGRADATION
    - [ ] Very stale odds (5 hours old) → DEGRADATION
    - [ ] Missing odds_timestamp → CRITICAL
  - [ ] Test form freshness:
    - [ ] Fresh form (1h old) → PASS
    - [ ] Old form (20h old) → PASS
    - [ ] Very old form (48h old) → DEGRADATION
    - [ ] Missing form_timestamp → DEGRADATION
  - [ ] Test injuries freshness:
    - [ ] Fresh injuries (1h old) → PASS
    - [ ] Old injuries (8h old) → PASS
    - [ ] Very old injuries (18h old) → DEGRADATION
    - [ ] Missing injuries_timestamp → DEGRADATION
  - [ ] Test overall validation:
    - [ ] All data fresh → PASS
    - [ ] Odds stale, form fresh → DEGRADATION
    - [ ] Fixture date in future → CRITICAL
    - [ ] Multiple degradations → DEGRADATION (aggregated)
  - [ ] Test validation summary logging (verify output format)
  - [ ] Target 85%+ code coverage for validator.py

- [ ] Task 15: Integration with consolidation pipeline (AC: #7)
  - [ ] Import validator into consolidation module
  - [ ] Call validator after consolidate_fixtures() returns
  - [ ] Ensure consolidated fixtures have all timestamp fields needed
  - [ ] Verify no data loss (validation only adds metadata, doesn't modify data)
  - [ ] Document call chain: fetch_all_data() → consolidate_fixtures() → validate_fixtures()

## Dev Notes

### Requirements Context Summary

**From Story 3.2 in development-stories.md (lines 253-275):**

User story: Validate that all data meets freshness requirements so analysis isn't based on stale information.
Acceptance criteria: Create validator module with freshness checks for fixtures, odds, form, injuries. Flag as CRITICAL (reject) or DEGRADATION (accept but lower confidence). Log validation results.
Definition of Done: Validator rejects fixtures with stale odds, accepts fixture but flags missing injury data, clear logging shows why each fixture passed/failed validation.

**From technical-spec.md (Data Consolidation Layer, lines 113-132):**

Data consolidation specification includes data quality rules:
- Reject odds > 1 hour stale
- Reject injuries > 12 hours stale
- Accept form data up to 24 hours old
- Head-to-head is static (no freshness check)
- Validation is critical for confidence scoring downstream

**Key Insight from Story 3.1:**

Story 3.1 consolidates fixtures from multiple sources and tracks source lineage with timestamps:
- form_data_timestamp: when form data was fetched
- injuries_timestamp: when fetched
- odds_timestamp: when fetched
- fixture_date: kickoff time (static from API-Football)

Story 3.2 receives consolidated Fixture objects and validates timestamps to ensure data freshness.

### Architecture Alignment

**Data Flow (from technical-spec.md):**

```
┌─────────────────────────────────┐
│ Consolidated Fixtures (3.1)     │ (Phase 3.1 Complete)
│ - All fields populated          │
│ - Source lineage tracked        │
│ - Timestamps on all data        │
└────────────────┬────────────────┘
                 │
        ┌────────▼────────────┐
        │ validator.py (3.2)  │ (Phase 3.2)
        │ Freshness checks    │
        │ Quality flags       │
        └────────┬────────────┘
                 │
        ┌────────▼────────────────────┐
        │ Output: Fixture[]           │
        │ - Validation status attached│
        │ - PASS/DEGRADATION/CRITICAL │
        │ - Ready for quality scoring │
        └────────┬────────────────────┘
                 │
        ┌────────▼────────────┐
        │ quality_scorer.py   │ (Story 3.3)
        │ (Phase 3.3)         │
        └────────────────────┘
```

**Integration Points:**

- Input: Output from Story 3.1 (consolidated Fixture[] with timestamps)
- Calls: None (pure data validation, no APIs)
- Called by: Story 3.3 (quality scoring - uses validation status)
- Output: Same Fixture[] with ValidationResult attached

**Validation Categories:**

| Status | Meaning | Action | Example |
|--------|---------|--------|---------|
| PASS | All data fresh | Accept fixture, full confidence | Odds 5min old, form 2h old |
| DEGRADATION | Some data stale | Accept fixture, lower confidence | Odds 75min old, form 20h old |
| CRITICAL | Required data missing/stale | Reject fixture | Odds > 1h old, fixture date in future |

### Learnings from Previous Story

**From Story 3.1: Data Consolidation Pipeline (Status: approved)**

**Existing Infrastructure for Reuse:**

1. **Consolidated Fixture Structure:**
   - All fixtures have timestamp fields from consolidation
   - source_lineage dict tracks which data came from which source
   - Timestamps stored in source_lineage: form_data_timestamp, injuries_timestamp, odds_timestamp
   - Fixture object itself has fixture_date (kickoff time)

2. **Error Handling Patterns (from Story 3.1):**
   - Returns fixtures with validation metadata (don't reject, mark status)
   - Logs at appropriate levels (INFO for pass, WARNING for issues)
   - Continues processing even when individual fixtures have issues

3. **Data Models Available (from Story 2.1):**
   - Fixture model already defined with required fields
   - Can add validation_result field or store separately
   - All source tracking available in consolidated fixtures

**Critical Notes for Story 3.2 Implementation:**

1. **Timestamp Locations:**
   - fixture_date: directly on Fixture object (from API-Football)
   - form_data_timestamp: in source_lineage dict or direct field
   - injuries_timestamp: in source_lineage dict or direct field
   - odds_timestamp: in source_lineage dict or direct field
   - Need to verify exact field names from Story 3.1 implementation

2. **Validation Strategy:**
   - Never reject without logging reason (critical for debugging)
   - DEGRADATION flags data quality issues but doesn't block fixture
   - Only CRITICAL completely rejects fixture
   - Story 3.3 (quality scoring) will penalize DEGRADATION further

3. **Timezone Handling:**
   - Use datetime.now(timezone.utc) for all timestamp comparisons
   - Ensure consolidated fixtures have timezone-aware datetimes
   - Handle conversion if Story 3.1 used naive datetimes

4. **Confidence Scoring Integration:**
   - Story 5.3 (confidence scoring) depends on these validation results
   - Validation should provide: which data type caused degradation, how old is it
   - Score calculation in Story 5.3 will use this info (e.g., odds 75min old → -5 pts)

[Source: docs/sprint-artifacts/3-1-create-data-consolidation-pipeline.md]
[Source: docs/technical-spec.md - System Architecture - Data Consolidation Layer]

### Project Structure Notes

**Expected File Structure (After Story 3.2):**

```
/src/bet_bot/
├── data/
│   ├── fetchers/
│   │   ├── __init__.py           (Story 2.5)
│   │   ├── api_football.py       (Story 2.2)
│   │   └── espn_scraper.py       (Story 2.3)
│   ├── consolidation/            (Story 3.1 created)
│   │   ├── __init__.py           (existing)
│   │   ├── consolidator.py       (existing)
│   │   ├── merger.py             (existing)
│   │   └── validator.py          (NEW - Story 3.2)
│   └── models/                   (Story 2.1)
│       ├── fixtures.py           (existing)
│       ├── form.py               (existing)
│       ├── injuries.py           (existing)
│       └── odds.py               (existing)
```

**Dependencies:**

- Existing: Fixture, Team, League Pydantic models (Story 2.1)
- Existing: consolidate_fixtures() output (Story 3.1)
- New imports needed: datetime, timezone, logging, asyncio (for async compatibility)
- New Pydantic model: ValidationResult
- No new external packages required

**Module Naming Conventions:**

- validator.py: Main validation orchestration
- `_validate_*()`: Internal helper functions for each data type
- ValidationResult: Result model (separate from Fixture)
- Use `_` prefix for internal helpers (not exported)

### Architectural Constraints & Decisions

**Validation Approach:**

- Non-invasive: Validation adds metadata to fixtures, doesn't modify data
- Permissive: Accept fixtures with DEGRADATION status, let downstream decide
- Observable: All validation reasons logged for debugging

**Timestamp Management:**

- All timestamps must be timezone-aware (UTC)
- Comparisons use datetime.now(timezone.utc)
- Missing timestamps treated as CRITICAL (data integrity issue)

**Error Handling Strategy:**

- No exceptions raised during validation (all fixtures processed)
- Validation failures logged, status attached to fixture
- Downstream stages (quality scoring, analysis) filter based on status

**Async Considerations:**

- validate_fixtures() marked async for consistency with pipeline
- No blocking calls (all operations are data validation)
- Can be awaited in orchestration layer

### References

- [Development Stories - Story 3.2](docs/development-stories.md#story-32-implement-data-freshness-validation) - User story definition
- [Technical Specification - Data Consolidation Layer](docs/technical-spec.md#2-data-consolidation-layer-dataconsolidation) - Data quality rules and freshness thresholds
- [Story 3.1 - Data Consolidation](docs/sprint-artifacts/3-1-create-data-consolidation-pipeline.md) - Consolidated fixture structure and timestamp fields
- [CLAUDE.md - Error Handling Patterns](CLAUDE.md#3-error-handling---mandatory-patterns) - Exception handling and logging standards

---

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/3-2-implement-data-freshness-validation.context.xml

### Agent Model Used

Claude Haiku 4.5 (claude-haiku-4-5-20251001)

### Debug Log References

### Completion Notes List

### File List
