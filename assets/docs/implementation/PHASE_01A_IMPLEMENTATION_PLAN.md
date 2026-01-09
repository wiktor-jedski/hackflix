# Phase 1a Implementation Plan

**Status:** Completed
**Date:** 2026-01-09

## Summary

This phase adds two features to the Hackflix library:
1. **Genre Search**: Search filter now searches both title AND genres (OR logic)
2. **Clear Filter Key**: Press X in Library view to clear the active search filter

## Requirements

| Requirement | Source | Implementation |
|-------------|--------|----------------|
| Search by genres | User request | `get_library_items()` searches `title LIKE ? OR genres LIKE ?` |
| Genre data from server | User clarification | Server provides `genres` field in content.json |
| Single search field | User clarification | One input searches both title and genres |
| X key clears filter | User request | X key in LIBRARY_ROOT state triggers `CLEAR_FILTER` action |

## Changes Made

### 1. Database Schema (`src/database/schema.py`)

Added `genres TEXT` column to `media_items` table:
```sql
CREATE TABLE IF NOT EXISTS media_items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('movie', 'series')),
    title TEXT NOT NULL,
    genres TEXT,  -- NEW: Comma-separated list of genres
    poster_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Database Manager (`src/database/db_manager.py`)

**2.1 `upsert_content()` (lines 111-130)**
- Extracts `genres` field from content.json items
- Stores genres in INSERT/UPDATE statement

**2.2 `get_library_items()` (lines 267-312)**
- SELECT now includes `genres` column
- WHERE clause changed from `title LIKE ?` to `(title LIKE ? OR genres LIKE ?)`
- Docstring updated to reflect genre search capability

### 3. Test Fixtures (`tests/conftest.py`)

Updated `sample_content_json` fixture with genres:
- Big Buck Bunny: "Animation, Comedy, Family"
- Sintel: "Animation, Fantasy, Action"
- Open Source Show: "Documentary, Technology"

### 4. Test Cases (`tests/test_database.py`)

Added 4 new tests:
- `test_upsert_content_with_genres` - Verifies genres are stored correctly
- `test_get_library_items_filter_by_genre` - Tests filtering by genre
- `test_get_library_items_filter_title_and_genre_or_logic` - Tests OR logic
- `test_upsert_content_without_genres` - Tests backwards compatibility

### 5. Architecture Documentation

**`assets/docs/architecture/02_DATA_DESIGN.md`**
- Added `genres` field to content.json examples (movie and series)
- Added `genres` column to media_items table definition

**`assets/docs/architecture/04_UI_UX_STATE_MACHINE.md`**
- Added X key to LIBRARY_ROOT state table: `CLEAR_FILTER` action
- Updated SEARCH_OVERLAY note to mention title+genre search

## Files Modified

| File | Change |
|------|--------|
| `src/database/schema.py` | Added `genres TEXT` column |
| `src/database/db_manager.py` | Updated upsert and search query |
| `tests/conftest.py` | Added genres to sample fixture |
| `tests/test_database.py` | Added 4 genre-related tests |
| `assets/docs/architecture/02_DATA_DESIGN.md` | Documented genres field |
| `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` | Documented X key |

## Migration Notes

- **No database migration required**: SQLite will add NULL values for existing rows when schema is re-initialized
- **Backwards compatible**: `genres` field is optional in content.json (uses `item.get("genres")`)
- **Server update required**: Server must include `genres` field in content.json for genre search to work

## Verification

Run tests:
```bash
uv run pytest tests/test_database.py -v
uv run pytest --cov=src --cov-report=term-missing tests/
```

Expected: All tests pass, 100% coverage on database module.

## UI Implementation Notes (Phase 3)

When implementing the UI in Phase 3:
1. **X key handler**: In `LibraryState.handle_input()`, map X key to clear the search filter
2. **Filter indicator**: Consider showing active filter text in the library header
3. **Genre display**: The `genres` field is now returned in `get_library_items()` and can be displayed in the UI
