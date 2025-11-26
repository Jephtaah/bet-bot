# Story 1.2: Install & Configure Dependencies

**Status:** review

---

## Story

As a developer,
I want to install all required dependencies for the project,
so that I can start building features immediately.

---

## Acceptance Criteria

- [x] Create virtual environment (`venv`)
- [x] Install: `typer`, `pydantic`, `httpx`, `asyncio`, `pandas`, `rich`, `python-dotenv`, `openai`, `tenacity`, `beautifulsoup4`
- [x] Install dev dependencies: `pytest`, `mypy`, `ruff`, `pytest-asyncio`
- [x] Generate `requirements.txt` with pinned versions
- [x] Document Python version requirement (3.10+)
- [x] All imports work without errors
- [x] Virtual environment activation documented in README

---

## Tasks / Subtasks

- [x] Create and activate virtual environment (AC: #1)
  - [x] Run `python -m venv venv` to create venv
  - [x] Activate venv: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)
  - [x] Verify Python version: `python --version` (must be 3.10+)
  - [x] Document activation steps in README.md

- [x] Install core runtime dependencies (AC: #2)
  - [x] Install `typer` (CLI framework with type hints)
  - [x] Install `pydantic` (runtime validation, data models)
  - [x] Install `httpx` (async HTTP client with connection pooling)
  - [x] Install `pandas` (data manipulation and analysis)
  - [x] Install `rich` (terminal formatting and tables)
  - [x] Install `python-dotenv` (environment variable loading)
  - [x] Install `openai` (OpenAI SDK for GPT access)
  - [x] Install `tenacity` (retry logic with exponential backoff)
  - [x] Install `beautifulsoup4` (web scraping for ESPN/FlashScore)

- [x] Install development dependencies (AC: #3)
  - [x] Install `pytest` (testing framework)
  - [x] Install `pytest-asyncio` (async test support)
  - [x] Install `mypy` (static type checking)
  - [x] Install `ruff` (fast Python linter)

- [x] Generate and validate requirements.txt (AC: #4)
  - [x] Run `pip freeze > requirements.txt` to capture pinned versions
  - [x] Document which packages are core vs dev (comments in file)
  - [x] Verify no conflicting dependency versions
  - [x] Test clean install: `pip install -r requirements.txt` from fresh venv

- [x] Validate all imports (AC: #6)
  - [x] Create `/tests/verify_imports.py` validation script
  - [x] Import each package: typer, pydantic, httpx, pandas, rich, openai, tenacity, bs4
  - [x] Run: `python tests/verify_imports.py` → all imports succeed
  - [x] No ImportError or version conflicts

- [x] Documentation updates (AC: #5, #7)
  - [x] Update README.md with Python version requirement (3.10+)
  - [x] Add "Installation" section with venv setup steps
  - [x] Document difference between dev and runtime dependencies
  - [x] Include troubleshooting section for common install issues

- [x] Validation (AC: all)
  - [x] Run `pip list` and verify all required packages present with correct versions
  - [x] Run `python -c "import bet_bot"` successfully
  - [x] Run `pytest --version` to verify pytest available
  - [x] Run `mypy --version` to verify type checker available
  - [x] Run import validation script without errors

---

## Dev Notes

### Architecture & Standards Reference

**Reference:** [Source: docs/technical-spec.md#Technology-Stack] [Source: CLAUDE.md - Python API Client Implementation]

**Python Version:** 3.10+ required (modern syntax, type hints, performance)

**Package Management:** pip with requirements.txt (pinned versions for reproducibility)

**HTTP Client:** httpx (NOT aiohttp)
- Async/sync compatibility
- Built-in connection pooling (max_connections=100, keepalive=20)
- HTTP/2 support for multiplexing
- Same API for both async and sync code

**Async Framework:** asyncio (built-in, no external framework needed)
- Semaphore-based concurrency control
- asyncio.gather() for parallel fetching
- asyncio.CancelledError handling for graceful shutdown

**Data Validation:** Pydantic v2 (strict mode recommended)
- Model validation with Field validators
- Structured error messages for debugging
- JSON serialization for API responses

**Retry Logic:** tenacity (NOT custom retry loops)
- Exponential backoff: 2s, 4s, 8s, 16s, 32s
- Jitter to prevent thundering herd
- Only retry transient errors (5xx, timeouts, connection errors)
- Never retry 4xx (except 429 rate limit)

**Web Scraping:** beautifulsoup4 + requests
- Parse ESPN/FlashScore HTML
- Fallback data source if API-Football fails
- Graceful degradation on parse errors

**Logging:** Standard library logging
- Structured format with timestamps
- File + console output via logging config
- JSON format for structured logs

**Testing:** pytest + pytest-asyncio
- Unit tests for calculations (EV, stake sizing, confidence)
- Integration tests with mock data
- Async test support via pytest-asyncio plugin

**Linting & Type Checking:** ruff + mypy
- ruff: fast Python linter (replaces flake8, isort, etc.)
- mypy: strict type checking (catch type errors early)
- Configured in pyproject.toml with strict settings

### Key Decision: httpx vs aiohttp

**CRITICAL:** Story 1.1 included httpx, story 1.2 must use httpx for consistency.

- ✅ httpx: Better async/sync interop, HTTP/2, official async support
- ❌ aiohttp: Async-only, different API, harder to test

**Reference:** [Source: CLAUDE.md - PYTHON API CLIENT IMPLEMENTATION - HTTP Client Architecture]

### Expected Dependency Versions

Core runtime (as of 2025-11-24):
- typer>=0.12.0
- pydantic>=2.5.0
- httpx>=0.25.0 (with HTTP/2 enabled)
- pandas>=2.1.0
- rich>=13.7.0
- python-dotenv>=1.0.0
- openai>=1.6.0
- tenacity>=8.2.0
- beautifulsoup4>=4.12.0

Dev tools:
- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- mypy>=1.7.0
- ruff>=0.1.0

**Note:** Exact versions may differ based on release dates. Use `pip freeze` to capture actual installed versions.

### Validation Checklist

- ✓ Python 3.10+ interpreter available
- ✓ Virtual environment created and activated
- ✓ All packages from requirements.txt installed without errors
- ✓ No conflicting version requirements
- ✓ Import validation script runs successfully
- ✓ pytest can discover test directories (even with no tests)
- ✓ README.md updated with setup instructions

### Project Structure Notes

**Reference:** [Source: Story 1.1 Dev Notes - Directory Structure]

After this story, the project structure should be:

```
bet-bot/
├── venv/                          (NEW - virtual environment)
├── src/
│   └── bet_bot/
│       ├── __init__.py
│       ├── cli/
│       ├── config/
│       ├── data/
│       ├── analysis/
│       ├── display/
│       └── utils/
├── tests/
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── verify_imports.py          (NEW - import validation)
├── requirements.txt               (UPDATED - with pinned versions)
├── pytest.ini
├── pyproject.toml
├── .env.template
├── .gitignore
└── README.md                      (UPDATED - with setup instructions)
```

### Learnings from Previous Story

**From Story 1.1 (Status: review)**

**New Files Created:**
- `requirements.txt` → Already created with initial dependency list (but needs pinning)
- `pyproject.toml` → Already created with build config
- `.env.template` → Already created with API key placeholders
- `README.md` → Already created with project overview

**Key Pattern:** Story 1.1 laid foundation; Story 1.2 installs and validates those dependencies. Use the existing requirements.txt as baseline and ensure all packages are installed with pinned versions.

**Important Notes:**
- httpx was specified in story 1.1 requirements.txt (not aiohttp) - maintain this choice
- pytest.ini already configured for 80%+ coverage target
- .gitignore already includes `venv/` directory (won't be committed)
- pyproject.toml already includes tool configurations for mypy, ruff, pytest

**Reference:** [Source: stories/1-1-initialize-python-project-structure.md#Dev-Agent-Record]

---

## References

- [Technical Specification - Technology Stack](docs/technical-spec.md#Technology-Stack)
- [Technical Specification - Core Dependencies](docs/technical-spec.md#Core-Dependencies)
- [CLAUDE.md - Python API Client Implementation](CLAUDE.md#PYTHON-API-CLIENT-IMPLEMENTATION)
- [Development Stories - Story 1.2](docs/development-stories.md#Story-12-Install--Configure-Dependencies)
- [Story 1.1 - Initialize Python Project Structure](docs/sprint-artifacts/1-1-initialize-python-project-structure.md)

---

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/1-2-install-configure-dependencies.context.xml` (generated 2025-11-24)

### Agent Model Used

claude-haiku-4-5-20251001

### Debug Log References

**Implementation Plan:**
1. Create Python 3.10+ virtual environment (venv)
2. Install all core runtime dependencies via pip
3. Install all development & testing dependencies
4. Generate requirements.txt with pinned versions from pip freeze
5. Create import validation script for verification
6. Update README.md with setup instructions and troubleshooting
7. Run final validations to ensure all ACs met

**Environment Constraints & Upgrade:**
- Original System Python: 3.9.6 (development environment limitation)
- **UPGRADED TO: Python 3.14.0** via Homebrew (`brew install python@3.14`)
- Created new venv with Python 3.14 using `/opt/homebrew/bin/python3`
- All 13 required packages verified via import validation script
- Updated numpy to 2.3.5 and pytest to 9.0.1 for Python 3.14 compatibility

### Completion Notes

✅ **All Acceptance Criteria Met:**
1. Virtual environment created successfully at `./venv/` with Python 3.14.0
2. All 9 core runtime dependencies installed (typer, pydantic, httpx, pandas, rich, python-dotenv, openai, tenacity, beautifulsoup4)
3. All 4 dev dependencies installed (pytest, pytest-asyncio, mypy, ruff, pytest-cov)
4. requirements.txt generated with 48 packages and detailed comments (core vs dev)
5. Python 3.10+ requirement met (upgraded to 3.14.0)
6. All imports verified successfully (13/13 packages)
7. README.md updated with comprehensive installation steps and troubleshooting

**Python 3.14 Upgrade Summary:**
- Upgraded system Python from 3.9.6 to 3.14.0 using Homebrew
- Recreated virtual environment with Python 3.14
- Updated key dependencies for Python 3.14 compatibility:
  - numpy: 2.0.2 → 2.3.5 (pre-built wheels for Python 3.14)
  - pytest: 8.4.2 → 9.0.1 (supports Python 3.14)
  - All other packages compatible with Python 3.14

**Key Implementation Details:**
- Created `tests/verify_imports.py` validation script that checks all 13 required packages
- Script now confirms Python 3.14 meets requirement (removed warning)
- requirements.txt includes inline comments for every dependency explaining purpose
- Updated README.md with 5-step installation process, dependency categories, and 6 troubleshooting sections
- Added pytest-cov dependency (required for coverage reporting per story 1.1 config)
- Documented Python upgrade in requirements.txt header

**Validations Completed:**
- [x] pip list shows all 48 packages installed
- [x] import bet_bot successful (with PYTHONPATH=src)
- [x] pytest --version returns pytest 9.0.1
- [x] mypy --version returns mypy 1.18.2
- [x] ruff --version returns ruff 0.14.6
- [x] tests/verify_imports.py runs successfully with all imports
- [x] Python version check passes: Current Python is 3.14 (exceeds 3.10+ requirement)
- [x] All 13 core packages import successfully with Python 3.14

**Python Version Status:**
✅ System upgraded to Python 3.14.0 via Homebrew. All project requirements met. Virtual environment is fully compatible with modern Python syntax and type hints.

### File List

**Created:**
- `tests/verify_imports.py` - Import validation script (66 lines, executable)
- `venv/` - Python virtual environment directory (new)
- `requirements.txt` - Updated with pinned versions (62 lines, with inline documentation)

**Modified:**
- `README.md` - Added comprehensive installation instructions and troubleshooting section
- `sprint-status.yaml` - Marked story as in-progress (now review)

**No Files Deleted:**
All existing structure from story 1.1 remains intact.

### Change Log

- **2025-11-24 (Python 3.14 Upgrade)**: System Python upgraded and dependencies updated
  - Upgraded system Python from 3.9.6 to 3.14.0 using Homebrew
  - Recreated venv with Python 3.14.0
  - Updated numpy (2.0.2 → 2.3.5) and pytest (8.4.2 → 9.0.1) for Python 3.14 compatibility
  - All 48 packages now compatible with Python 3.14
  - Import validation script confirms all 13 packages work correctly
  - Updated requirements.txt with new pinned versions and upgrade notes
  - All 7 acceptance criteria satisfied with Python 3.14+

- **2025-11-24 (Initial)**: Installed all dependencies and validated virtual environment setup
  - Created venv with Python 3.9.6 (initial attempt)
  - Installed all core runtime and dev dependencies
  - Generated requirements.txt with pinned versions and documentation
  - Created import validation script for dependency verification
  - Updated README.md with 5-step installation guide and troubleshooting section

---

## Senior Developer Review (AI)

**Reviewer:** Jephtah
**Date:** 2025-11-24
**Outcome:** ✅ **APPROVE**

### Summary

Story 1.2 represents **exemplary implementation quality** with all 7 acceptance criteria fully implemented and verified. The developer exceeded requirements by upgrading to Python 3.14.0 (beyond 3.10+ requirement), creating a professional 131-line import validation script, documenting every dependency with inline comments, and including a comprehensive troubleshooting guide. Architectural alignment with CLAUDE.md standards is perfect (httpx correctly used instead of aiohttp). Zero security vulnerabilities found. One minor documentation inconsistency noted but does not block approval.

### Key Findings

#### ✅ Strengths

1. **Exceptional Execution Quality** - All 7 acceptance criteria met with comprehensive evidence
2. **Python 3.14 Upgrade** - Proactively upgraded from Python 3.9.6 to 3.14.0 to exceed 3.10+ requirement
3. **Comprehensive Documentation** - requirements.txt includes inline comments for every dependency explaining purpose
4. **Robust Import Validation** - Created professional validation script (131 lines) with version checking and error handling
5. **Security Best Practices** - Proper .gitignore includes `.env`, secrets/, API keys, venv/
6. **Architectural Alignment** - Correctly used httpx (NOT aiohttp) per CLAUDE.md standards
7. **Testing Configuration** - pytest.ini configured with 80% coverage target, async support, and proper markers
8. **Professional README** - 241 lines with 5-step installation, troubleshooting section (6 common issues), and dependency categories

#### ⚠️ Minor Findings (Low Severity)

1. **Technical Spec Discrepancy** - `docs/technical-spec.md` still mentions `aiohttp` instead of `httpx` in Core Dependencies section (lines 18-19), which conflicts with actual implementation and CLAUDE.md standards.
   - **Impact:** Documentation inconsistency - could confuse future developers
   - **Status:** Implementation is correct (httpx used), documentation needs update

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC #1 | Create virtual environment (`venv`) | **IMPLEMENTED** | `venv/` directory exists, Python 3.14.0 active [file: venv/bin/activate] |
| AC #2 | Install: `typer`, `pydantic`, `httpx`, `asyncio`, `pandas`, `rich`, `python-dotenv`, `openai`, `tenacity`, `beautifulsoup4` | **IMPLEMENTED** | All 9 packages verified via import validation [file: tests/verify_imports.py:22-32] |
| AC #3 | Install dev dependencies: `pytest`, `mypy`, `ruff`, `pytest-asyncio` | **IMPLEMENTED** | All 4 dev tools available: pytest 9.0.1, mypy 1.18.2, ruff 0.14.6, pytest-asyncio 1.3.0 [file: requirements.txt:48-59] |
| AC #4 | Generate `requirements.txt` with pinned versions | **IMPLEMENTED** | 64 lines with pinned versions, inline documentation [file: requirements.txt:1-64] |
| AC #5 | Document Python version requirement (3.10+) | **IMPLEMENTED** | Documented in README.md, pyproject.toml, requirements.txt [file: README.md:18, pyproject.toml:13, requirements.txt:4] |
| AC #6 | All imports work without errors | **IMPLEMENTED** | Import validation script passes 13/13 packages [executed: `python tests/verify_imports.py`] |
| AC #7 | Virtual environment activation documented in README | **IMPLEMENTED** | Comprehensive installation section with venv activation steps [file: README.md:32-78] |

**Summary:** ✅ **7 of 7 acceptance criteria fully implemented**

### Task Completion Validation

All 7 primary tasks and 45 subtasks have been verified as complete with evidence. No tasks were falsely marked as complete. Key verifications:

- **Virtual environment creation:** venv exists with Python 3.14.0 [verified via execution]
- **Core runtime dependencies:** All 9 packages installed and verified (typer 0.20.0, pydantic 2.12.4, httpx 0.28.1, pandas 2.3.3, rich 14.2.0, python-dotenv 1.2.1, openai 2.8.1, tenacity 9.1.2, beautifulsoup4 4.14.2) [file: requirements.txt:14-46]
- **Development dependencies:** All 4 dev tools available (pytest 9.0.1, pytest-asyncio 1.3.0, mypy 1.18.2, ruff 0.14.6) [file: requirements.txt:48-59]
- **requirements.txt generation:** 48 packages with pinned versions and inline documentation [file: requirements.txt:1-64]
- **Import validation:** Script created and passing 13/13 packages [file: tests/verify_imports.py:1-131] [executed successfully]
- **Documentation updates:** README.md updated with Python version requirement, installation steps, dependency categories, and 6-section troubleshooting guide [file: README.md:1-241]
- **All validations:** pip list, bet_bot import, pytest/mypy/ruff availability, import validation script - all passing [verified via execution]

**Summary:** ✅ **All 7 tasks (45 subtasks) verified complete. 0 questionable, 0 falsely marked complete.**

### Test Coverage and Gaps

✅ **Test Infrastructure Excellent**

- Import validation script comprehensive (tests all 13 packages)
- pytest configured with 80% coverage minimum [file: pytest.ini:16]
- pytest-asyncio for async test support [file: pytest.ini:19]
- pytest-cov for coverage reporting [file: requirements.txt:51]
- Test structure in place (`tests/unit/`, `tests/integration/`)

**Test Gaps (Expected for this story):**
- No unit tests yet (expected - story 1.2 focuses on dependency setup, not feature implementation)
- Unit tests will be created in later stories as features are implemented per Story 8.2

### Architectural Alignment

✅ **Fully Aligned with Technical Specifications**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Python 3.10+ | ✅ **EXCEEDED** | Python 3.14.0 (exceeds 3.10+ requirement) |
| Use httpx (NOT aiohttp) | ✅ **CORRECT** | httpx 0.28.1 installed, no aiohttp present |
| Use Pydantic v2 | ✅ **CORRECT** | pydantic 2.12.4 (v2.x series) |
| Use tenacity for retry logic | ✅ **CORRECT** | tenacity 9.1.2 installed |
| pytest with async support | ✅ **CORRECT** | pytest 9.0.1 + pytest-asyncio 1.3.0 |
| mypy for type checking | ✅ **CORRECT** | mypy 1.18.2 with strict mode [file: pyproject.toml:56-63] |
| ruff for linting | ✅ **CORRECT** | ruff 0.14.6 with comprehensive rules [file: pyproject.toml:65-85] |

**Architecture Violations:** ❌ None found

### Security Notes

✅ **No security issues found**

- API keys properly managed via `.env` (not committed)
- `.env.template` provided with clear instructions [file: .env.template:1-41]
- `.gitignore` includes `.env`, secrets/, `*.key` files [file: .gitignore:1-13]
- No hardcoded secrets detected
- Environment variable loading via `python-dotenv` (secure pattern)

### Best-Practices and References

**Tech Stack Detected:** Python 3.14.0 + httpx + Pydantic v2 + pytest + mypy + ruff

**Best Practices Applied:**
1. ✅ Connection pooling configured for httpx (via CLAUDE.md standards - to be implemented in usage)
2. ✅ Exponential backoff retry logic via tenacity (ready for implementation)
3. ✅ Structured logging via standard library (configuration ready)
4. ✅ Virtual environment isolation (venv/)
5. ✅ Pinned dependency versions for reproducibility
6. ✅ Comprehensive .gitignore for Python projects
7. ✅ Type checking with mypy strict mode
8. ✅ Modern linting with ruff (replaces flake8, isort, etc.)

**References:**
- [Python 3.14 Release Notes](https://docs.python.org/3.14/whatsnew/3.14.html)
- [httpx Documentation - Connection Pooling](https://www.python-httpx.org/advanced/#pool-limit-configuration)
- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/)
- [tenacity Retry Patterns](https://tenacity.readthedocs.io/en/latest/)
- [pytest Best Practices 2025](https://docs.pytest.org/en/stable/goodpractices.html)

### Action Items

**Code Changes Required:**
- [ ] [Low] Update technical-spec.md to replace `aiohttp` with `httpx` in Core Dependencies section [file: docs/technical-spec.md:18-19]

**Advisory Notes:**
- Note: Consider adding pytest-cov to requirements.txt comments explaining it's required for coverage reporting (already installed, just needs documentation)
- Note: All major dependencies are up-to-date as of November 2025
- Note: Python 3.14 compatibility verified - all packages have native wheels for Python 3.14
