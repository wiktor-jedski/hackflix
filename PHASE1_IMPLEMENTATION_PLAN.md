# Phase 1 Implementation Plan: Server-Based Catalog

**Goal**: Implement server-based catalog system with offline-first SQLite database, enabling streamlined content discovery and download workflow.

**Timeline Estimate**: 3-4 weeks of development

**Success Criteria**:
- ✅ catalog.json schema defined and documented
- ✅ 5-10 curated titles hosted on GitHub Pages
- ✅ Local SQLite database with catalog data
- ✅ Manual sync functionality with progress dialog
- ✅ Incremental sync based on timestamps
- ✅ Basic catalog display (can be minimal, full UI is Phase 2)

---

## Task Breakdown

### Task 1: Design catalog.json Schema (Priority: Critical, Est: 4 hours)

**Objective**: Define the complete data structure for catalog.json that will serve both movies and series.

**Implementation Steps**:

1. **Create schema documentation** (`docs/catalog_schema.md`):
   - Document all required and optional fields
   - Provide examples for movies and series
   - Define validation rules
   - Document versioning strategy

2. **Define schema structure**:

```json
{
  "version": "1.0.0",
  "last_updated": "2025-01-06T12:00:00Z",
  "movies": [
    {
      "id": "movie_001",                    // Unique identifier (required)
      "title": "Movie Title",               // Display name (required)
      "year": 2024,                         // Release year (required)
      "genre": ["Action", "Sci-Fi"],        // Array of genres (required)
      "description": "Short description",   // 1-2 sentences (required)
      "magnet_link": "magnet:?xt=...",     // BitTorrent magnet URI (required)
      "file_size": 2147483648,              // Bytes (required)
      "subtitle_languages": ["en"],         // Available subtitle languages (required)
      "poster_url": "https://...",          // TMDB/IMDb poster URL (optional)
      "imdb_id": "tt1234567",              // IMDb identifier (optional)
      "tmdb_id": 12345,                     // TMDB identifier (optional)
      "runtime": 120,                       // Minutes (optional)
      "video_quality": "1080p",             // Resolution indicator (optional)
      "video_codec": "H.264",               // Codec info (optional)
      "audio_codec": "AAC"                  // Audio codec (optional)
    }
  ],
  "series": [
    {
      "id": "series_001",                   // Unique identifier (required)
      "title": "Series Title",              // Display name (required)
      "year": 2024,                         // First air year (required)
      "genre": ["Drama"],                   // Array of genres (required)
      "description": "Short description",   // 1-2 sentences (required)
      "poster_url": "https://...",          // TMDB/IMDb poster URL (optional)
      "imdb_id": "tt7654321",              // IMDb identifier (optional)
      "tmdb_id": 54321,                     // TMDB identifier (optional)
      "seasons": [
        {
          "season_number": 1,               // Season index (required)
          "magnet_link": "magnet:?xt=...",  // Full season torrent (required)
          "file_size": 5368709120,          // Total season size in bytes (required)
          "episode_count": 8,               // Number of episodes (required)
          "year": 2024,                     // Season air year (optional)
          "video_quality": "1080p",         // Resolution (optional)
          "episodes": [                     // Episode metadata (optional, for UI)
            {
              "episode_number": 1,
              "title": "Pilot",
              "runtime": 45
            }
          ]
        }
      ]
    }
  ],
  "genres": [                               // Available genre list for filtering
    "Action",
    "Comedy",
    "Drama",
    "Sci-Fi",
    "Thriller",
    "Horror",
    "Romance",
    "Documentary"
  ]
}
```

3. **Create validation script** (`scripts/validate_catalog.py`):
   - Validate JSON syntax
   - Check required fields
   - Validate magnet link format
   - Verify timestamp format
   - Check for duplicate IDs

**Acceptance Criteria**:
- [ ] Schema documented with all fields explained
- [ ] Example catalog.json with sample data
- [ ] Validation script passes on sample data
- [ ] Schema supports both movies and series

**Dependencies**: None

---

### Task 2: Set Up GitHub Pages Hosting (Priority: High, Est: 2 hours)

**Objective**: Configure GitHub Pages to host catalog.json and make it accessible via HTTPS.

**Implementation Steps**:

1. **Create GitHub repository** (or use existing):
   - Repository name: `hackflix-catalog` (or use branch in main repo)
   - Public repository (required for GitHub Pages)

2. **Set up GitHub Pages**:
   - Enable GitHub Pages in repository settings
   - Source: `main` branch, `/docs` folder or root
   - Custom domain: optional

3. **Create directory structure**:
```
hackflix-catalog/
├── README.md                 # Catalog documentation
├── catalog.json              # Main catalog file
├── catalog-schema.json       # JSON Schema definition (optional)
├── scripts/
│   ├── validate_catalog.py   # Validation script
│   └── update_catalog.py     # Helper to update timestamps
└── assets/                   # Optional: host poster images
    └── posters/
```

4. **Configure catalog URL**:
   - Base URL: `https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json`
   - Add URL to client configuration file

5. **Set up GitHub Actions** (optional but recommended):
   - Auto-validate catalog.json on push
   - Update `last_updated` timestamp automatically
   - Generate changelog from commits

**Example GitHub Action** (`.github/workflows/validate-catalog.yml`):
```yaml
name: Validate Catalog
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Validate catalog.json
        run: python scripts/validate_catalog.py
```

**Acceptance Criteria**:
- [ ] GitHub Pages URL accessible via browser
- [ ] catalog.json downloadable via HTTPS
- [ ] Validation runs on commits (if using Actions)
- [ ] README documents catalog structure and update process

**Dependencies**: Task 1 (schema definition)

---

### Task 3: Build Initial Catalog with 5-10 Titles (Priority: High, Est: 6 hours)

**Objective**: Curate and populate catalog with initial content selection.

**Implementation Steps**:

1. **Content selection**:
   - Choose 5-10 movies/series based on criteria:
     - Personal favorites
     - High IMDb/TMDB ratings (7.5+)
     - Reliable torrent availability
     - Good subtitle availability
   - Mix of genres for variety

2. **Gather metadata** for each title:
   - Use TMDB API or OMDb API to fetch:
     - Official title, year, genre
     - Plot summary/description
     - Poster URL
     - Runtime, IMDb ID
   - Manually verify magnet links from trusted torrent sources
   - Check file sizes and quality (prefer 1080p, reasonable size)

3. **Create metadata collection script** (`scripts/collect_metadata.py`):
```python
import requests
import json
from datetime import datetime

TMDB_API_KEY = "your_api_key"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

def fetch_movie_metadata(tmdb_id):
    """Fetch movie metadata from TMDB"""
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    data = response.json()

    return {
        "id": f"movie_{tmdb_id}",
        "title": data["title"],
        "year": int(data["release_date"][:4]),
        "genre": [g["name"] for g in data["genres"]],
        "description": data["overview"][:200] + "...",
        "poster_url": f"https://image.tmdb.org/t/p/w500{data['poster_path']}",
        "imdb_id": data["imdb_id"],
        "tmdb_id": tmdb_id,
        "runtime": data["runtime"],
        # Manual fields:
        "magnet_link": "",  # Add manually
        "file_size": 0,     # Add manually
        "subtitle_languages": ["en"]
    }

def fetch_series_metadata(tmdb_id):
    """Fetch TV series metadata from TMDB"""
    # Similar implementation for series
    pass
```

4. **Populate catalog.json**:
   - Run metadata collection script
   - Manually add magnet links (from 1337x, RARBG alternatives, etc.)
   - Calculate or estimate file sizes
   - Verify all required fields present

5. **Initial content suggestions** (examples):
   - Movies: Inception, The Shawshank Redemption, The Matrix, Interstellar, The Dark Knight
   - Series: Breaking Bad S1, Game of Thrones S1, Stranger Things S1

**Acceptance Criteria**:
- [ ] 5-10 titles in catalog.json
- [ ] All required fields populated
- [ ] Magnet links verified (seeders available)
- [ ] Metadata accurate and well-formatted
- [ ] catalog.json passes validation script
- [ ] File committed to GitHub Pages repository

**Dependencies**: Task 1 (schema), Task 2 (hosting setup)

---

### Task 4: Design SQLite Database Schema (Priority: Critical, Est: 3 hours)

**Objective**: Define local database structure for catalog caching, download state, and watch history.

**Implementation Steps**:

1. **Create database schema** (`source/db_schema.py`):

```python
import sqlite3
from datetime import datetime

DATABASE_VERSION = 1
DATABASE_FILE = "hackflix.db"

# SQL Schema definitions
SCHEMA = """
-- Metadata table
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Movies table
CREATE TABLE IF NOT EXISTS movies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    description TEXT,
    magnet_link TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    poster_url TEXT,
    imdb_id TEXT,
    tmdb_id INTEGER,
    runtime INTEGER,
    video_quality TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movie genres (many-to-many)
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    PRIMARY KEY (movie_id, genre),
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

-- Series table
CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    description TEXT,
    poster_url TEXT,
    imdb_id TEXT,
    tmdb_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Series genres (many-to-many)
CREATE TABLE IF NOT EXISTS series_genres (
    series_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    PRIMARY KEY (series_id, genre),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Seasons table
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    magnet_link TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    episode_count INTEGER NOT NULL,
    year INTEGER,
    video_quality TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (series_id, season_number),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Download state table
CREATE TABLE IF NOT EXISTS download_state (
    id TEXT PRIMARY KEY,  -- movie_id or season_id
    type TEXT NOT NULL,   -- 'movie' or 'season'
    status TEXT NOT NULL, -- 'available', 'downloading', 'ready', 'failed'
    progress REAL DEFAULT 0.0,  -- 0.0 to 100.0
    phase TEXT,           -- 'video', 'subtitles', 'translation'
    phase_progress REAL DEFAULT 0.0,
    error_message TEXT,
    download_path TEXT,   -- Local file path when downloaded
    torrent_info_hash TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Watch history table (for series)
CREATE TABLE IF NOT EXISTS watch_history (
    series_id TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    file_path TEXT,
    last_position INTEGER DEFAULT 0,  -- milliseconds
    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (series_id, season_number, episode_number),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Subtitle cache table
CREATE TABLE IF NOT EXISTS subtitle_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_path TEXT NOT NULL,
    subtitle_path TEXT NOT NULL,
    language TEXT NOT NULL,  -- 'en', 'pl', etc.
    source TEXT,  -- 'opensubtitles', 'manual', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (video_path, language)
);

-- API usage tracking (for cost management)
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,  -- 'gemini', 'opensubtitles', 'tts'
    operation TEXT NOT NULL,  -- 'translate', 'search', 'generate'
    tokens_used INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
CREATE INDEX IF NOT EXISTS idx_series_year ON series(year);
CREATE INDEX IF NOT EXISTS idx_download_state_status ON download_state(status);
CREATE INDEX IF NOT EXISTS idx_watch_history_series ON watch_history(series_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_service_date ON api_usage(service, timestamp);
"""

def initialize_database(db_path=DATABASE_FILE):
    """Initialize database with schema"""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # Set database version
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("db_version", str(DATABASE_VERSION))
    )

    # Set initial catalog sync timestamp
    conn.execute(
        "INSERT OR IGNORE INTO metadata (key, value) VALUES (?, ?)",
        ("last_catalog_sync", "1970-01-01T00:00:00Z")
    )

    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")

if __name__ == "__main__":
    initialize_database()
```

2. **Create database migration system** (`source/db_migrations.py`):
   - Support for future schema changes
   - Version tracking
   - Safe migration execution

3. **Add database utilities** (`source/db_utils.py`):
   - Connection pooling
   - Common queries as helper functions
   - Transaction management

**Acceptance Criteria**:
- [ ] Schema script creates all tables successfully
- [ ] Foreign key constraints properly defined
- [ ] Indexes created for common queries
- [ ] Migration system in place for future changes
- [ ] Database initialization runs without errors

**Dependencies**: None (can run in parallel with Tasks 1-3)

---

### Task 5: Implement Catalog Manager (Priority: Critical, Est: 12 hours)

**Objective**: Create Python module to fetch, parse, and sync catalog.json with local SQLite database.

**Implementation Steps**:

1. **Create `source/catalog_manager.py`**:

```python
"""
Catalog manager for fetching and syncing movie/series catalog.
"""

import requests
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
import traceback

# Configuration
DEFAULT_CATALOG_URL = "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json"
DATABASE_FILE = "hackflix.db"
SYNC_TIMEOUT = 30  # seconds

class CatalogManager(QObject):
    """Manages catalog fetching and local database synchronization"""

    # Signals
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(str, int)  # (message, percentage)
    sync_completed = pyqtSignal(int, int)  # (movies_count, series_count)
    sync_error = pyqtSignal(str)
    catalog_updated = pyqtSignal()  # Emit when local catalog changes

    def __init__(self, catalog_url=DEFAULT_CATALOG_URL, db_path=DATABASE_FILE):
        super().__init__()
        self.catalog_url = catalog_url
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database exists and is initialized"""
        # Import and run schema initialization if needed
        from source.db_schema import initialize_database
        # Check if database exists, initialize if not
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'db_version'")
            result = cursor.fetchone()
            conn.close()
            if result is None:
                initialize_database(self.db_path)
        except sqlite3.OperationalError:
            initialize_database(self.db_path)

    def fetch_catalog(self) -> Optional[Dict]:
        """Fetch catalog.json from server"""
        try:
            response = requests.get(self.catalog_url, timeout=SYNC_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch catalog: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid catalog JSON: {str(e)}")

    def get_last_sync_timestamp(self) -> str:
        """Get timestamp of last successful sync"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_catalog_sync'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "1970-01-01T00:00:00Z"

    def set_last_sync_timestamp(self, timestamp: str):
        """Update last sync timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("last_catalog_sync", timestamp)
        )
        conn.commit()
        conn.close()

    def sync_catalog(self):
        """
        Fetch and sync catalog with local database.
        Performs incremental sync based on last_updated timestamp.
        """
        try:
            self.sync_started.emit()
            self.sync_progress.emit("Fetching catalog from server...", 10)

            # Fetch remote catalog
            catalog = self.fetch_catalog()
            remote_timestamp = catalog.get("last_updated", "")
            local_timestamp = self.get_last_sync_timestamp()

            self.sync_progress.emit("Comparing versions...", 20)

            # Check if update needed
            if remote_timestamp <= local_timestamp:
                self.sync_progress.emit("Catalog is up to date", 100)
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                movie_count = cursor.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
                series_count = cursor.execute("SELECT COUNT(*) FROM series").fetchone()[0]
                conn.close()
                self.sync_completed.emit(movie_count, series_count)
                return

            # Perform sync
            self.sync_progress.emit("Updating local database...", 40)
            movies_synced = self._sync_movies(catalog.get("movies", []))

            self.sync_progress.emit("Syncing series...", 70)
            series_synced = self._sync_series(catalog.get("series", []))

            # Update last sync timestamp
            self.set_last_sync_timestamp(remote_timestamp)

            self.sync_progress.emit("Sync complete!", 100)
            self.sync_completed.emit(movies_synced, series_synced)
            self.catalog_updated.emit()

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            traceback.print_exc()
            self.sync_error.emit(error_msg)

    def _sync_movies(self, movies: List[Dict]) -> int:
        """Sync movies to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        count = 0

        for movie in movies:
            try:
                # Insert or update movie
                cursor.execute("""
                    INSERT OR REPLACE INTO movies
                    (id, title, year, description, magnet_link, file_size,
                     poster_url, imdb_id, tmdb_id, runtime, video_quality, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    movie["id"],
                    movie["title"],
                    movie["year"],
                    movie.get("description", ""),
                    movie["magnet_link"],
                    movie["file_size"],
                    movie.get("poster_url"),
                    movie.get("imdb_id"),
                    movie.get("tmdb_id"),
                    movie.get("runtime"),
                    movie.get("video_quality")
                ))

                # Clear existing genres
                cursor.execute("DELETE FROM movie_genres WHERE movie_id = ?", (movie["id"],))

                # Insert genres
                for genre in movie.get("genre", []):
                    cursor.execute(
                        "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                        (movie["id"], genre)
                    )

                # Initialize download state if not exists
                cursor.execute("""
                    INSERT OR IGNORE INTO download_state
                    (id, type, status, progress)
                    VALUES (?, 'movie', 'available', 0.0)
                """, (movie["id"],))

                count += 1
            except Exception as e:
                print(f"Error syncing movie {movie.get('id', 'unknown')}: {e}")

        conn.commit()
        conn.close()
        return count

    def _sync_series(self, series_list: List[Dict]) -> int:
        """Sync series to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        count = 0

        for series in series_list:
            try:
                # Insert or update series
                cursor.execute("""
                    INSERT OR REPLACE INTO series
                    (id, title, year, description, poster_url, imdb_id, tmdb_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    series["id"],
                    series["title"],
                    series["year"],
                    series.get("description", ""),
                    series.get("poster_url"),
                    series.get("imdb_id"),
                    series.get("tmdb_id")
                ))

                # Clear existing genres
                cursor.execute("DELETE FROM series_genres WHERE series_id = ?", (series["id"],))

                # Insert genres
                for genre in series.get("genre", []):
                    cursor.execute(
                        "INSERT INTO series_genres (series_id, genre) VALUES (?, ?)",
                        (series["id"], genre)
                    )

                # Sync seasons
                for season in series.get("seasons", []):
                    cursor.execute("""
                        INSERT OR REPLACE INTO seasons
                        (series_id, season_number, magnet_link, file_size,
                         episode_count, year, video_quality)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        series["id"],
                        season["season_number"],
                        season["magnet_link"],
                        season["file_size"],
                        season["episode_count"],
                        season.get("year"),
                        season.get("video_quality")
                    ))

                    # Initialize download state for season
                    season_id = f"{series['id']}_s{season['season_number']}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO download_state
                        (id, type, status, progress)
                        VALUES (?, 'season', 'available', 0.0)
                    """, (season_id,))

                count += 1
            except Exception as e:
                print(f"Error syncing series {series.get('id', 'unknown')}: {e}")

        conn.commit()
        conn.close()
        return count

    def get_all_movies(self) -> List[Dict]:
        """Get all movies from local database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.*, GROUP_CONCAT(mg.genre) as genres,
                   ds.status, ds.progress
            FROM movies m
            LEFT JOIN movie_genres mg ON m.id = mg.movie_id
            LEFT JOIN download_state ds ON m.id = ds.id
            GROUP BY m.id
            ORDER BY m.title
        """)

        movies = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parse genres string to list
        for movie in movies:
            movie['genre'] = movie['genres'].split(',') if movie['genres'] else []
            del movie['genres']

        return movies

    def get_all_series(self) -> List[Dict]:
        """Get all series from local database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.*, GROUP_CONCAT(sg.genre) as genres
            FROM series s
            LEFT JOIN series_genres sg ON s.id = sg.series_id
            GROUP BY s.id
            ORDER BY s.title
        """)

        series = [dict(row) for row in cursor.fetchall()]

        # Get seasons for each series
        for show in series:
            show['genre'] = show['genres'].split(',') if show['genres'] else []
            del show['genres']

            cursor.execute("""
                SELECT se.*, ds.status, ds.progress
                FROM seasons se
                LEFT JOIN download_state ds ON
                    ds.id = (se.series_id || '_s' || se.season_number)
                WHERE se.series_id = ?
                ORDER BY se.season_number
            """, (show['id'],))

            show['seasons'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return series

    def get_movies_by_genre(self, genre: str) -> List[Dict]:
        """Get movies filtered by genre"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT m.*, GROUP_CONCAT(mg.genre) as genres,
                   ds.status, ds.progress
            FROM movies m
            LEFT JOIN movie_genres mg ON m.id = mg.movie_id
            LEFT JOIN download_state ds ON m.id = ds.id
            WHERE m.id IN (
                SELECT movie_id FROM movie_genres WHERE genre = ?
            )
            GROUP BY m.id
            ORDER BY m.title
        """, (genre,))

        movies = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for movie in movies:
            movie['genre'] = movie['genres'].split(',') if movie['genres'] else []
            del movie['genres']

        return movies
```

2. **Add configuration file** (`source/config.py`):
```python
"""Application configuration"""

import os
from pathlib import Path

# Paths
APP_DIR = Path(__file__).parent.parent
DATABASE_FILE = APP_DIR / "hackflix.db"
DOWNLOAD_DIR = Path.home() / "Videos" / "HackFlix"

# Catalog
CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json"
)

# Ensure directories exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
```

**Acceptance Criteria**:
- [ ] CatalogManager class implemented with all methods
- [ ] Fetches catalog.json successfully
- [ ] Incremental sync based on timestamps works
- [ ] Movies and series inserted into SQLite correctly
- [ ] Download state initialized for all items
- [ ] Signals emitted correctly for UI updates
- [ ] Error handling for network failures
- [ ] Unit tests for sync logic (optional but recommended)

**Dependencies**: Task 1 (schema), Task 4 (database schema)

---

### Task 6: Build Manual Sync UI (Priority: High, Est: 8 hours)

**Objective**: Create UI component for triggering catalog sync with progress feedback.

**Implementation Steps**:

1. **Create sync dialog** (`source/sync_dialog.py`):

```python
"""
Catalog sync progress dialog
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                            QProgressBar, QPushButton, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSlot
from source.catalog_manager import CatalogManager
import traceback

class SyncWorker(QThread):
    """Worker thread for catalog sync"""
    def __init__(self, catalog_manager):
        super().__init__()
        self.catalog_manager = catalog_manager

    def run(self):
        """Execute sync in background thread"""
        try:
            self.catalog_manager.sync_catalog()
        except Exception as e:
            print(f"Sync worker error: {e}")
            traceback.print_exc()

class SyncDialog(QDialog):
    """Progress dialog for catalog synchronization"""

    def __init__(self, catalog_manager, parent=None):
        super().__init__(parent)
        self.catalog_manager = catalog_manager
        self.sync_worker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize UI components"""
        self.setWindowTitle(self.tr("Update Catalog"))
        self.setModal(True)
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel(self.tr("Preparing to sync..."))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Details text (initially hidden)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setVisible(False)
        layout.addWidget(self.details_text)

        # Show details button
        self.details_button = QPushButton(self.tr("Show Details"))
        self.details_button.clicked.connect(self._toggle_details)
        self.details_button.setVisible(False)
        layout.addWidget(self.details_button)

        # Close button (initially disabled)
        self.close_button = QPushButton(self.tr("Close"))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        layout.addWidget(self.close_button)

    def _connect_signals(self):
        """Connect catalog manager signals"""
        self.catalog_manager.sync_started.connect(self._on_sync_started)
        self.catalog_manager.sync_progress.connect(self._on_sync_progress)
        self.catalog_manager.sync_completed.connect(self._on_sync_completed)
        self.catalog_manager.sync_error.connect(self._on_sync_error)

    def _toggle_details(self):
        """Toggle details text visibility"""
        visible = self.details_text.isVisible()
        self.details_text.setVisible(not visible)
        self.details_button.setText(
            self.tr("Hide Details") if not visible else self.tr("Show Details")
        )

    def start_sync(self):
        """Start the sync process"""
        self.sync_worker = SyncWorker(self.catalog_manager)
        self.sync_worker.finished.connect(self._on_worker_finished)
        self.sync_worker.start()

    @pyqtSlot()
    def _on_sync_started(self):
        """Handle sync started signal"""
        self.status_label.setText(self.tr("Synchronizing catalog..."))
        self.progress_bar.setValue(0)

    @pyqtSlot(str, int)
    def _on_sync_progress(self, message, percentage):
        """Handle progress updates"""
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)
        self.details_text.append(f"[{percentage}%] {message}")

    @pyqtSlot(int, int)
    def _on_sync_completed(self, movies_count, series_count):
        """Handle successful sync completion"""
        message = self.tr(
            f"Sync completed successfully!\n\n"
            f"Movies: {movies_count}\n"
            f"Series: {series_count}"
        )
        self.status_label.setText(message)
        self.progress_bar.setValue(100)
        self.close_button.setEnabled(True)
        self.details_text.append("\n✓ Sync completed successfully")

    @pyqtSlot(str)
    def _on_sync_error(self, error_message):
        """Handle sync errors"""
        self.status_label.setText(self.tr("Sync failed!"))
        self.details_text.append(f"\n✗ ERROR: {error_message}")
        self.details_text.setVisible(True)
        self.details_button.setVisible(True)
        self.details_button.setText(self.tr("Hide Details"))
        self.progress_bar.setValue(0)
        self.close_button.setEnabled(True)

    @pyqtSlot()
    def _on_worker_finished(self):
        """Handle worker thread completion"""
        if self.sync_worker:
            self.sync_worker.deleteLater()
            self.sync_worker = None

    def closeEvent(self, event):
        """Handle dialog close"""
        if self.sync_worker and self.sync_worker.isRunning():
            # Don't allow close while syncing
            event.ignore()
        else:
            event.accept()
```

2. **Add sync action to main window** (`source/movie_player.py`):
   - Add menu item or toolbar button for "Update Catalog"
   - Connect to sync dialog
   - Show notification on completion

3. **Integration code**:
```python
# In MoviePlayerApp.__init__()
self.catalog_manager = CatalogManager()

# Add menu action
sync_action = QAction("Update Catalog", self)
sync_action.triggered.connect(self.show_sync_dialog)
# Add to menu/toolbar

def show_sync_dialog(self):
    """Show catalog sync dialog"""
    from source.sync_dialog import SyncDialog
    dialog = SyncDialog(self.catalog_manager, self)
    dialog.start_sync()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        # Refresh catalog display
        self.refresh_catalog_view()
```

**Acceptance Criteria**:
- [ ] Sync dialog displays properly
- [ ] Progress updates in real-time
- [ ] Success message shows movie/series counts
- [ ] Error messages display with "Show Details" option
- [ ] Dialog prevents closing during sync
- [ ] UI thread remains responsive during sync
- [ ] Catalog view refreshes after successful sync

**Dependencies**: Task 5 (CatalogManager)

---

### Task 7: Basic Catalog Display (Priority: Medium, Est: 6 hours)

**Objective**: Create minimal catalog view to verify sync works (full UI is Phase 2).

**Implementation Steps**:

1. **Create simple catalog tab** (`source/catalog_tab_minimal.py`):
```python
"""
Minimal catalog display for Phase 1 testing
(Will be replaced with full UI in Phase 2)
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget,
                            QListWidgetItem, QLabel, QPushButton,
                            QHBoxLayout, QTabWidget)
from PyQt5.QtCore import pyqtSlot

class MinimalCatalogTab(QWidget):
    """Simple catalog viewer for Phase 1"""

    def __init__(self, catalog_manager):
        super().__init__()
        self.catalog_manager = catalog_manager
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(self.tr("Catalog (Phase 1 - Basic View)"))
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header)

        # Tabs for Movies/Series
        self.tabs = QTabWidget()

        # Movies list
        self.movies_list = QListWidget()
        self.movies_list.itemDoubleClicked.connect(self._on_movie_clicked)
        self.tabs.addTab(self.movies_list, self.tr("Movies"))

        # Series list
        self.series_list = QListWidget()
        self.series_list.itemDoubleClicked.connect(self._on_series_clicked)
        self.tabs.addTab(self.series_list, self.tr("Series"))

        layout.addWidget(self.tabs)

        # Refresh button
        refresh_btn = QPushButton(self.tr("Refresh"))
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

    def _connect_signals(self):
        """Connect catalog manager signals"""
        self.catalog_manager.catalog_updated.connect(self.refresh)

    @pyqtSlot()
    def refresh(self):
        """Refresh catalog display"""
        # Clear lists
        self.movies_list.clear()
        self.series_list.clear()

        # Load movies
        movies = self.catalog_manager.get_all_movies()
        for movie in movies:
            status = movie.get('status', 'available')
            progress = movie.get('progress', 0)
            item_text = f"{movie['title']} ({movie['year']}) - {status}"
            if status == 'downloading':
                item_text += f" {progress:.0f}%"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, movie)
            self.movies_list.addItem(item)

        # Load series
        series = self.catalog_manager.get_all_series()
        for show in series:
            item_text = f"{show['title']} ({show['year']}) - {len(show['seasons'])} seasons"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, show)
            self.series_list.addItem(item)

    @pyqtSlot(QListWidgetItem)
    def _on_movie_clicked(self, item):
        """Handle movie click"""
        movie = item.data(Qt.UserRole)
        print(f"Movie clicked: {movie['title']}")
        # TODO: Show movie details or start download

    @pyqtSlot(QListWidgetItem)
    def _on_series_clicked(self, item):
        """Handle series click"""
        series = item.data(Qt.UserRole)
        print(f"Series clicked: {series['title']}")
        # TODO: Show series/season selection
```

2. **Integrate into main window**:
```python
# In MoviePlayerApp._setup_ui_views_and_layouts()
from source.catalog_tab_minimal import MinimalCatalogTab

self.catalog_tab = MinimalCatalogTab(self.catalog_manager)
self.tab_widget.addTab(self.catalog_tab, self.tr("Catalog (Test)"))
```

**Acceptance Criteria**:
- [ ] Catalog tab appears in main window
- [ ] Movies list displays after sync
- [ ] Series list displays with season count
- [ ] Status and progress shown for items
- [ ] Refresh updates display
- [ ] Double-click prints item info (for testing)

**Dependencies**: Task 5 (CatalogManager), Task 6 (sync UI)

---

## Implementation Order

**Week 1**:
1. Task 1: Design catalog.json schema (Day 1)
2. Task 4: Design SQLite schema (Day 1-2)
3. Task 2: Set up GitHub Pages (Day 2)
4. Task 3: Build initial catalog (Day 3-4)

**Week 2**:
5. Task 5: Implement CatalogManager (Day 5-7)
6. Unit testing for CatalogManager (Day 7)

**Week 3**:
7. Task 6: Build sync UI (Day 8-9)
8. Task 7: Basic catalog display (Day 10)
9. Integration testing (Day 10-11)

**Week 4** (Buffer):
10. Bug fixes and polish
11. Documentation updates
12. Performance testing on Raspberry Pi

---

## Testing Strategy

### Unit Tests

Create `tests/test_catalog_manager.py`:
```python
import unittest
from unittest.mock import Mock, patch
from source.catalog_manager import CatalogManager
import tempfile
import os

class TestCatalogManager(unittest.TestCase):

    def setUp(self):
        """Create temp database for testing"""
        self.db_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.db_file.name
        self.catalog_manager = CatalogManager(
            catalog_url="http://test.com/catalog.json",
            db_path=self.db_path
        )

    def tearDown(self):
        """Clean up temp database"""
        os.unlink(self.db_path)

    @patch('requests.get')
    def test_fetch_catalog_success(self, mock_get):
        """Test successful catalog fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "last_updated": "2025-01-06T12:00:00Z",
            "movies": [],
            "series": []
        }
        mock_get.return_value = mock_response

        catalog = self.catalog_manager.fetch_catalog()
        self.assertIsNotNone(catalog)
        self.assertEqual(catalog["last_updated"], "2025-01-06T12:00:00Z")

    def test_sync_movies(self):
        """Test movie sync to database"""
        movies = [
            {
                "id": "test_001",
                "title": "Test Movie",
                "year": 2024,
                "genre": ["Action"],
                "magnet_link": "magnet:?xt=test",
                "file_size": 1000000000
            }
        ]

        count = self.catalog_manager._sync_movies(movies)
        self.assertEqual(count, 1)

        # Verify database
        all_movies = self.catalog_manager.get_all_movies()
        self.assertEqual(len(all_movies), 1)
        self.assertEqual(all_movies[0]["title"], "Test Movie")

if __name__ == '__main__':
    unittest.main()
```

### Integration Tests

1. **Test full sync workflow**:
   - Mock catalog.json response
   - Verify database populated correctly
   - Check download_state initialized

2. **Test incremental sync**:
   - Initial sync with old timestamp
   - Update catalog with new timestamp
   - Verify only changes synced

3. **Test UI integration**:
   - Trigger sync from UI
   - Verify progress updates
   - Check catalog display refreshes

### Manual Testing on Raspberry Pi

1. Install on fresh Pi 5 setup
2. Run initial sync
3. Verify download states
4. Test network disconnection handling
5. Measure sync performance
6. Check memory usage

---

## Risk Assessment & Mitigation

### Risk 1: GitHub Pages Rate Limiting
**Impact**: High
**Probability**: Low
**Mitigation**:
- Add caching headers to catalog.json
- Implement exponential backoff
- Add manual catalog.json override (local file path)

### Risk 2: Magnet Links Become Dead
**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- Regular catalog maintenance schedule
- Add magnet health check script
- Document process for updating dead links

### Risk 3: Database Corruption
**Impact**: High
**Probability**: Low
**Mitigation**:
- Implement database backups
- Add repair/rebuild function
- Include database integrity checks

### Risk 4: Sync Conflicts (Concurrent Access)
**Impact**: Medium
**Probability**: Low
**Mitigation**:
- Use SQLite WAL mode
- Add sync locking mechanism
- Prevent multiple simultaneous syncs

### Risk 5: Performance on Raspberry Pi
**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- Use database indexes effectively
- Batch database operations
- Test on actual Pi 5 hardware early
- Optimize queries if slow

---

## Configuration Files

### `.env` additions:
```
# Catalog configuration
CATALOG_URL=https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
DATABASE_PATH=./hackflix.db
```

### `source/config.py`:
```python
import os
from pathlib import Path

# Catalog
CATALOG_URL = os.getenv("CATALOG_URL", "https://default-url/catalog.json")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./hackflix.db"))

# Sync
SYNC_TIMEOUT = 30
AUTO_SYNC_ON_STARTUP = False  # For future: auto-sync
SYNC_CHECK_INTERVAL = 86400  # Seconds (24 hours)
```

---

## Documentation Deliverables

1. **API Documentation** (`docs/catalog_api.md`):
   - catalog.json schema
   - CatalogManager API reference
   - Database schema documentation

2. **User Guide** (`docs/sync_guide.md`):
   - How to update catalog
   - Troubleshooting sync issues
   - Understanding availability status

3. **Developer Guide** (`docs/phase1_development.md`):
   - Setting up development environment
   - Running tests
   - Contributing to catalog

---

## Success Metrics

Phase 1 is considered complete when:

- [ ] All 7 tasks completed
- [ ] catalog.json with 5-10 titles hosted and accessible
- [ ] Manual sync works without errors
- [ ] Catalog data visible in minimal UI
- [ ] Database properly stores movies and series
- [ ] Incremental sync functions correctly
- [ ] Unit tests pass (>80% coverage on CatalogManager)
- [ ] Integration tests pass
- [ ] Tested on Raspberry Pi 5
- [ ] Documentation complete
- [ ] Code reviewed and committed to repository

---

## Next Steps (Phase 2 Preview)

After Phase 1 completion, Phase 2 will focus on:
- Removing legacy tabs (Downloads, Filmweb)
- Building full catalog UI with list view
- Genre filtering tabs
- Availability status indicators
- Download integration with catalog
- 3-phase progress display

Phase 1 provides the foundation for Phase 2's UI improvements.
