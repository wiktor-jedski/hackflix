#!/usr/bin/env python3
"""
Maintenance utility for HackFlix database and downloads.

Provides tools to:
- Reset download states
- Clean up downloaded files
- Force catalog sync
- View current state
"""

import os
import sys
import sqlite3
import shutil
from pathlib import Path


class HackFlixMaintenance:
    def __init__(self, db_path='hackflix.db', download_dir='~/Videos/HackFlix'):
        self.db_path = db_path
        self.download_dir = os.path.expanduser(download_dir)

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_downloads(self):
        """Show all downloads and their states"""
        conn = self._get_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("DOWNLOAD STATES")
        print("="*80)

        cursor.execute("""
            SELECT ds.id, ds.type, ds.status, ds.progress, ds.phase,
                   COALESCE(m.title, s.title) as title
            FROM download_state ds
            LEFT JOIN movies m ON ds.id = m.id
            LEFT JOIN series s ON ds.id = s.id
            ORDER BY ds.updated_at DESC
        """)

        for row in cursor.fetchall():
            print(f"\nID: {row['id']}")
            print(f"  Title: {row['title']}")
            print(f"  Type: {row['type']}")
            print(f"  Status: {row['status']}")
            print(f"  Progress: {row['progress']:.1f}%")
            print(f"  Phase: {row['phase']}")

        conn.close()
        print("\n" + "="*80 + "\n")

    def reset_download(self, item_id):
        """
        Reset download state for specific item and clean up files

        Args:
            item_id: Movie or season ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get current state
        cursor.execute("SELECT * FROM download_state WHERE id = ?", (item_id,))
        state = cursor.fetchone()

        if not state:
            print(f"❌ No download state found for {item_id}")
            conn.close()
            return

        print(f"\n🔄 Resetting download: {item_id}")
        print(f"  Current status: {state['status']}")
        print(f"  Current progress: {state['progress']:.1f}%")

        # Reset download state
        cursor.execute("""
            UPDATE download_state
            SET status = 'available',
                progress = 0.0,
                phase = NULL,
                phase_progress = 0.0,
                video_progress = 0.0,
                subtitle_progress = 0.0,
                translation_progress = 0.0,
                download_path = NULL,
                subtitle_path = NULL,
                translated_subtitle_path = NULL,
                torrent_info_hash = NULL,
                error_message = NULL,
                error_details = NULL,
                started_at = NULL,
                completed_at = NULL,
                failed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (item_id,))

        conn.commit()
        conn.close()

        print(f"✅ Download state reset to 'available'")

        # Clean up downloaded files
        self._cleanup_files(item_id)

    def reset_all_downloads(self):
        """Reset all downloads to available state"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM download_state WHERE status != 'available'")
        items = cursor.fetchall()
        conn.close()

        if not items:
            print("ℹ️  No downloads to reset")
            return

        print(f"\n🔄 Resetting {len(items)} downloads...")
        for row in items:
            self.reset_download(row['id'])

        print(f"\n✅ All downloads reset!")

    def _cleanup_files(self, item_id):
        """
        Clean up downloaded files for an item

        Args:
            item_id: Movie or season ID
        """
        if not os.path.exists(self.download_dir):
            print(f"  ℹ️  Download directory doesn't exist: {self.download_dir}")
            return

        print(f"  🧹 Cleaning up files in {self.download_dir}...")

        # Get movie/series title from database
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(m.title, s.title) as title
            FROM download_state ds
            LEFT JOIN movies m ON ds.id = m.id
            LEFT JOIN series s ON ds.id = s.id
            WHERE ds.id = ?
        """, (item_id,))

        row = cursor.fetchone()
        conn.close()

        if not row or not row['title']:
            print(f"  ⚠️  Could not find title for {item_id}")
            return

        title = row['title']

        # Search for files/folders matching the title
        files_removed = 0
        dirs_removed = 0

        for item in os.listdir(self.download_dir):
            item_path = os.path.join(self.download_dir, item)

            # Simple matching: check if title appears in filename/dirname
            if title.lower() in item.lower():
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        files_removed += 1
                        print(f"    Removed file: {item}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        dirs_removed += 1
                        print(f"    Removed directory: {item}")
                except Exception as e:
                    print(f"    ⚠️  Error removing {item}: {e}")

        if files_removed == 0 and dirs_removed == 0:
            print(f"  ℹ️  No files found to clean up")
        else:
            print(f"  ✅ Cleaned up {files_removed} files, {dirs_removed} directories")

    def force_sync(self):
        """Force catalog sync by resetting last sync timestamp"""
        conn = self._get_connection()
        cursor = conn.cursor()

        print("\n🔄 Forcing catalog sync...")
        print("  Resetting last_catalog_sync to 1970-01-01...")

        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value)
            VALUES ('last_catalog_sync', '1970-01-01T00:00:00Z')
        """)

        conn.commit()
        conn.close()

        print("✅ Last sync timestamp reset")
        print("ℹ️  Run catalog sync in the app to fetch latest catalog")

    def show_magnet_links(self):
        """Show magnet links for all movies"""
        conn = self._get_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("MOVIE MAGNET LINKS")
        print("="*80)

        cursor.execute("SELECT id, title, substr(magnet_link, 1, 80) as magnet FROM movies")

        for row in cursor.fetchall():
            print(f"\n{row['title']} ({row['id']})")
            print(f"  {row['magnet']}...")

        conn.close()
        print("\n" + "="*80 + "\n")


def main():
    """Command-line interface"""
    maintenance = HackFlixMaintenance()

    if len(sys.argv) < 2:
        print("HackFlix Maintenance Utility")
        print("\nUsage:")
        print("  python maintenance.py list              - List all downloads")
        print("  python maintenance.py reset <item_id>   - Reset specific download")
        print("  python maintenance.py reset-all         - Reset all downloads")
        print("  python maintenance.py force-sync        - Force catalog sync")
        print("  python maintenance.py magnet-links      - Show magnet links")
        print("\nOther utilities:")
        print("  python detect_completed.py              - Detect and mark completed downloads")
        print("  uv run python test_sync.py [--force]    - Test catalog sync")
        print("\nExamples:")
        print("  python maintenance.py reset movie_27205")
        print("  python maintenance.py reset-all")
        print("  python detect_completed.py")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'list':
        maintenance.list_downloads()

    elif command == 'reset':
        if len(sys.argv) < 3:
            print("❌ Error: Please specify item_id")
            print("Usage: python maintenance.py reset <item_id>")
            sys.exit(1)
        item_id = sys.argv[2]
        maintenance.reset_download(item_id)

    elif command == 'reset-all':
        maintenance.reset_all_downloads()

    elif command == 'force-sync':
        maintenance.force_sync()

    elif command == 'magnet-links':
        maintenance.show_magnet_links()

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
