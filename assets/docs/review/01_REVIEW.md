# Phase 1 Code Review: Foundation & Database

## 1. Critical Bugs & Functional Issues
*These issues must be fixed to ensure the application functions according to the specifications.*

### 1.1. Missing Logic in `update_file_state`
**File:** `src/database/db_manager.py`
**Issue:** The function accepts a `progress` argument, but the SQL statement ignores it.
**Fix:** Update the SQL query to include the progress column.
```python
# Current
cursor.execute("UPDATE video_files SET state = ? WHERE id = ?", (state.value, file_id))

# Required
# Note: video_files doesn't strictly have a 'download_progress' column in schema.py?
# Check Schema: video_files has 'state', seasons has 'download_progress'.
# ARCHITECTURE CHECK: 02_DATA_DESIGN says "Polling loop updates download_progress in DB."
# video_files table definition in 02_DATA_DESIGN does NOT list a download_progress column (only seasons does).
# However, for movies, where is progress stored? 
# If video_files represents a movie, it needs a progress column, or the UI won't show percentage.
```
**Action Required:**
1.  **Schema Change:** Add `download_progress INTEGER DEFAULT 0` to `video_files` table in `schema.py`.
2.  **Code Fix:** Update `update_file_state` in `db_manager.py` to write this value.

### 1.2. Missing Environment Variable Validation
**File:** `src/config.py`
**Issue:** `CATALOG_URL` is retrieved from the environment but is not validated in `check_required_env_vars()`.
**Fix:** Add `CATALOG_URL` to the list of checked variables in `check_required_env_vars`.

### 1.3. Hardcoded Debug Mode
**File:** `src/main.py`
**Issue:** `setup_logging(debug=True)` is hardcoded with a `# TODO`.
**Fix:** Control this via an environment variable (e.g., `DEBUG=true`), defaulting to `False` for production safety.

---

## 2. Review Questions

### 2.1. Tests
> *Why is tempfile imported in conftest, but not used?*

`conftest.py` uses the `tmp_path` fixture (from pytest), not the `tempfile` module. **Action:** Remove unused import.

> *Tests for None return types*

Methods like `get_video_file` return `dict | None`. The current tests assume the record exists. **Action:** Add negative test cases (e.g., `test_get_nonexistent_video_file`) to ensure the application handles `None` without crashing.

---

## 3. Architecture & Standards Compliance

### 3.1. Log Directory Conflict
**Observation:**
*   `02_DATA_DESIGN` specifies: `~/.config/pi-player/logs/`
*   `06_DEV_STANDARDS` specifies: `hackflix/logs/` (Project root)
*   **Current Code:** Uses `CONFIG_DIR / "logs"` (Matches `02_DATA_DESIGN`).

**Verdict:** The code is correct for a "set-top box" appliance. Logs should be in the XDG Config path in production, not inside the code folder.
**Action:** Update `06_DEV_STANDARDS.md` to match the code/Data Design. Change the directory to ~/.config/hackflix/logs/ to align with project name, both in code and in docs.

### 3.2. Unused Imports (Linting)
The following files have unused imports that must be cleaned up to pass strict linting:
*   `tests/conftest.py`: `import tempfile`
*   `tests/test_config.py`: `import os`, `import pytest`, `from src.config import LOG_FORMAT`
*   `tests/test_database.py`: `import pytest`

### 3.3. Test Coverage Gaps
*   **`ensure_directories`**: This *is* technically tested in `test_config.py` inside `test_creates_directories`, but the imports in the test file are messy.
*   **`check_dependencies`**: In `main.py`, this function imports libraries inside a try/except block. This is hard to test without mocking `sys.modules`.
*   **Recommendation:** Add `pytest-cov` to `pyproject.toml` and run `pytest --cov=src` to objectively verify the 100% line coverage requirement mentioned in your review.

---

## 4. Summary of Required Changes for Phase 1

1.  **Schema Update:** Add `download_progress` column to `video_files` table in `schema.py`.
2.  **Bug Fix:** Update `db_manager.update_file_state` to actually use the `progress` argument and write to the new column.
3.  **Bug Fix:** Add `CATALOG_URL` validation in `config.py`.
4.  **Refactor:** Remove unused imports in all test files.
5.  **Refactor:** Make `debug=True` in `main.py` configurable via env var.
6.  **Testing:** Add negative tests for DB getters (handling `None` results).
7.  **Tooling:** Add `pytest-cov` to project dependencies.
