#!/usr/bin/env python3
"""
Test catalog sync manually
"""

import sys
from PyQt5.QtCore import QCoreApplication
from source.catalog_manager import CatalogManager

def main():
    app = QCoreApplication(sys.argv)

    manager = CatalogManager()

    # Connect signals to see progress
    manager.sync_started.connect(lambda: print("🔄 Sync started..."))
    manager.sync_progress.connect(lambda msg, pct: print(f"  [{pct:3d}%] {msg}"))
    manager.sync_completed.connect(
        lambda movies, series: print(f"✅ Sync completed: {movies} movies, {series} series")
    )
    manager.sync_error.connect(lambda err: print(f"❌ Sync error: {err}"))

    # Check if force sync requested
    force = '--force' in sys.argv

    if force:
        print("Running FORCE sync (ignoring timestamps)...\n")
        manager.sync_catalog(force=True)
    else:
        print("Running normal sync...\n")
        print("(Use --force to ignore timestamps)\n")
        manager.sync_catalog(force=False)

    # Show updated magnet links
    import sqlite3
    conn = sqlite3.connect('hackflix.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, substr(magnet_link, 1, 80) as magnet FROM movies WHERE id IN ('movie_27205', 'movie_155')")

    print("\nUpdated magnet links:")
    for row in cursor.fetchall():
        print(f"\n{row['title']} ({row['id']})")
        print(f"  {row['magnet']}...")

    conn.close()

if __name__ == '__main__':
    main()
