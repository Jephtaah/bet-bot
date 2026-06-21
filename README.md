# bet-bot

**Positive Expected Value Detection Tool for Football Betting**

A CLI tool that identifies value betting opportunities by analyzing fixture data, team form, injuries, and odds to detect positive expected value (EV) betting edges.

## Features

- Parallel async data fetching from multiple sources (API-Football, ESPN, FlashScore)
- AI-powered probability estimation using OpenAI
- Expected value calculation and edge detection
- Confidence scoring based on data quality
- Kelly Criterion-based stake sizing
- Beautiful terminal output with Rich

## Requirements

- **Python 3.10+** (for modern syntax and type hints)
- API Keys:
  - OpenAI API Key (required)
  - API-Football Key (required)
  - Odds-API Key (optional backup)

## Installation

### Step 1: Clone the repository
```bash
git clone (https://github.com/Jephtaah/bet-bot)
cd bet-bot
```

### Step 2: Create a virtual environment

Create an isolated Python environment to avoid dependency conflicts:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR on Windows:
venv\Scripts\activate
```

**Verify Python version in the venv:**
```bash
python --version  # Should be 3.10+
```

### Step 3: Install dependencies

Install all project dependencies from requirements.txt (pinned versions for reproducibility):

```bash
pip install -r requirements.txt
```

This installs:
- **Core Runtime**: typer, pydantic, httpx, pandas, rich, openai, tenacity, beautifulsoup4, python-dotenv
- **Development**: pytest, pytest-asyncio, mypy, ruff

### Step 4: Verify installation

Validate that all dependencies are correctly installed:

```bash
python tests/verify_imports.py
```

Expected output: "All imports successful! Virtual environment is ready!"

### Step 5: Configure environment variables

```bash
cp .env.template .env
# Edit .env and add your API keys
```

## Dependency Categories

### Core Runtime Dependencies (9 packages)
These are required for the application to run:
- **typer**: CLI framework with type hints
- **pydantic**: Data validation with strict mode
- **httpx**: Async HTTP client with connection pooling (NOT requests/aiohttp)
- **pandas**: Data manipulation and analysis
- **rich**: Beautiful terminal formatting and tables
- **python-dotenv**: Environment variable management
- **openai**: OpenAI API SDK for GPT access
- **tenacity**: Retry logic with exponential backoff
- **beautifulsoup4**: Web scraping for ESPN/FlashScore fallback

### Development & Testing (4 packages)
Optional but recommended for development:
- **pytest**: Testing framework for unit/integration tests
- **pytest-asyncio**: Async test support
- **mypy**: Static type checking with strict mode
- **ruff**: Fast Python linter (replaces flake8/isort)

## Usage

```bash
# Analyze today's fixtures
python -m bet_bot.cli analyze --bankroll 1000

# Filter by league
python -m bet_bot.cli analyze --bankroll 1000 --league "Championship"

# Set custom EV threshold
python -m bet_bot.cli analyze --bankroll 1000 --threshold 5.0

# Enable verbose logging
python -m bet_bot.cli analyze --bankroll 1000 --verbose
```

## Project Structure

```
bet-bot/
├── src/
│   └── bet_bot/          # Main package
│       ├── cli/          # CLI interface
│       ├── config/       # Configuration management
│       ├── data/         # Data fetching and consolidation
│       ├── analysis/     # AI analysis and edge detection
│       ├── display/      # Terminal output formatting
│       └── utils/        # Utility functions
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── config/               # Configuration files
├── requirements.txt      # Python dependencies
├── pytest.ini            # Test configuration
└── .env.template         # Environment variable template
```

## Development

Run tests:
```bash
pytest
```

Type checking:
```bash
mypy src/
```

Linting:
```bash
ruff check src/
```

## Troubleshooting

### Python version too old
**Error:** `Python 3.9 detected, but 3.10+ is required`

**Solution:** Upgrade Python to 3.10 or later. Modern Python syntax and type hints require 3.10+.

Currently running: **Python 3.14.0** (installed via Homebrew)

```bash
# Check your Python version
python --version

# If system Python is too old, upgrade to 3.14 via Homebrew (macOS):
brew install python@3.14

# Or use alternative methods:
# - macOS: brew install python@3.13 or python@3.12
# - Ubuntu/Debian: apt-get install python3.14 or python3.13
# - Windows: Download from python.org (latest version)
```

### Virtual environment not activated
**Error:** `pip command not found` or wrong Python version

**Solution:** Make sure to activate the virtual environment:

```bash
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Verify activation (prompt should show (venv))
```

### ImportError or ModuleNotFoundError
**Error:** `No module named 'httpx'` or similar

**Solution:** Ensure all dependencies are installed:

```bash
# First, verify venv is activated
python --version  # Should be 3.10+

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
python tests/verify_imports.py
```

### Dependency conflicts
**Error:** `pip install` fails with version conflicts

**Solution:** Clear the cache and reinstall:

```bash
pip cache purge
pip install --force-reinstall -r requirements.txt
```

### Can't import bet_bot module
**Error:** `No module named 'bet_bot'`

**Solution:** Ensure you're in the project root and the package structure is correct:

```bash
# Verify you're in the right directory
pwd  # Should show .../bet-bot

# Check structure
ls src/bet_bot/__init__.py  # Should exist

# Try importing directly
python -c "import sys; sys.path.insert(0, 'src'); import bet_bot"
```

## License

MIT

## Author

Jephtah
