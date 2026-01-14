## Commands

```bash
# Setup
uv sync

# Run application
uv run python src/main.py

# Run single test file
uv run pytest tests/test_database.py

# Run tests with coverage
uv run pytest --cov=src tests/ --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run ty check
```

## Architecture

**Signal-Driven MVC with PyQt5:**
- **View (UI):** Dumb components that display data and emit signals. No business logic. Located in `src/ui/`.
- **Controller:** Connects Views to Services, handles state and routing. `src/controllers/app_controller.py`.
- **Model:** Raw sqlite3 with per-operation connections (no ORM). Located in `src/database/`.
- **Services:** QThread-based background workers for Downloads, Pipeline, Playback. Located in `src/services/`.

**Critical Rule:** The UI thread must never perform file I/O or network requests synchronously.

## Key Implementation Rules

1. **Type hints mandatory** on all function signatures
2. **No logic in Views** - UI classes must not import services or database
3. **Specific exception handling** - never bare `try: except:`
4. **Per-operation DB connections** - open/close for each operation
5. **Tests required** before committing any code change

## Test Coverage Requirements

**Target: 100% line coverage.** After implementing any feature, run:

```bash
uv run pytest --cov=src --cov-report=term-missing tests/
```

If 100% coverage is not achievable, document the specific reason below.

### Accepted Coverage Exceptions

| File | Coverage | Reason |
|------|----------|--------|

### Coverage Rules

1. **All error handling paths must be tested** - use `unittest.mock` to simulate failures
2. **All branches must be tested** - both `if` and `else` paths (e.g., upsert existing vs new records)
3. **Negative tests required** - test that functions return `None`/empty list for nonexistent records
4. **No untested code in production modules** - exceptions must be listed in the table above with justification

## State Enumerations

**Download State:** `PENDING` → `QUEUED` → `DOWNLOADING` → `COMPLETED` / `ERROR`

**Pipeline State:** `NONE` → `FETCHING_SUBS` → `TRANSLATING` → `SUBS_READY` → `GENERATING_TTS` → `MIXING_AUDIO` → `VOICEOVER_READY` / `FAILED`

## Error Handling

- Show toast notifications for user-facing errors (toasts stack visually)
- Log all errors to `app.log`
- Failed jobs marked as `Error` in DB for retry
- Auto-resume incomplete downloads/processing on startup
