#!/usr/bin/env python3
"""
Migration: Add subtitle metadata table

Adds a table to store OpenSubtitles file_id and translation requirements
per movie/episode.
"""

import sqlite3
import sys


def migrate(db_path='hackflix.db'):
    """Add subtitle metadata table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Creating subtitle_metadata table...")

    # Create subtitle metadata table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subtitle_metadata (
            movie_id TEXT,
            episode_id TEXT,
            file_id TEXT,                      -- OpenSubtitles file ID for direct download
            language TEXT NOT NULL,            -- Subtitle language (e.g., 'en', 'pl')
            needs_translation BOOLEAN DEFAULT FALSE,  -- Whether subtitle needs translation to Polish
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (movie_id, episode_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
            CHECK ((movie_id IS NOT NULL AND episode_id IS NULL) OR
                   (movie_id IS NULL AND episode_id IS NOT NULL))
        )
    """)

    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_subtitle_metadata_movie
        ON subtitle_metadata(movie_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_subtitle_metadata_episode
        ON subtitle_metadata(episode_id)
    """)

    conn.commit()

    print("✅ Migration complete!")
    print("\nTable structure:")
    cursor.execute("PRAGMA table_info(subtitle_metadata)")
    for row in cursor.fetchall():
        print(f"  {row}")

    conn.close()


if __name__ == '__main__':
    migrate()
