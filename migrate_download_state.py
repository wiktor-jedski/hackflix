"""
Database migration: Add component status tracking to download_state table

Adds fields:
- video_status: Track video download completion separately
- subtitle_status: Track subtitle download completion
- translation_status: Track translation completion
- subtitle_quota_date: Track when subtitle quota resets (for series)
- subtitle_quota_used: Track how many subtitles downloaded today

This enables parallel downloads and smart resume functionality.
"""

import sqlite3
import sys
from datetime import date

DATABASE_FILE = "hackflix.db"


def migrate_download_state(db_path: str = DATABASE_FILE):
    """
    Add component status tracking columns to download_state table.

    Args:
        db_path: Path to database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print(f"🔄 Migrating database: {db_path}")
        print("   Adding component status columns to download_state...")

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(download_state)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        migrations = []

        # Add video_status column
        if 'video_status' not in existing_columns:
            migrations.append((
                "ALTER TABLE download_state ADD COLUMN video_status TEXT DEFAULT 'pending' "
                "CHECK(video_status IN ('pending', 'downloading', 'completed', 'failed', 'not_needed'))"
            ))

        # Add subtitle_status column
        if 'subtitle_status' not in existing_columns:
            migrations.append((
                "ALTER TABLE download_state ADD COLUMN subtitle_status TEXT DEFAULT 'pending' "
                "CHECK(subtitle_status IN ('pending', 'downloading', 'completed', 'failed', 'not_needed'))"
            ))

        # Add translation_status column
        if 'translation_status' not in existing_columns:
            migrations.append((
                "ALTER TABLE download_state ADD COLUMN translation_status TEXT DEFAULT 'pending' "
                "CHECK(translation_status IN ('pending', 'translating', 'completed', 'failed', 'not_needed'))"
            ))

        # Add subtitle quota tracking
        if 'subtitle_quota_date' not in existing_columns:
            migrations.append((
                "ALTER TABLE download_state ADD COLUMN subtitle_quota_date TEXT"
            ))

        if 'subtitle_quota_used' not in existing_columns:
            migrations.append((
                "ALTER TABLE download_state ADD COLUMN subtitle_quota_used INTEGER DEFAULT 0"
            ))

        if not migrations:
            print("   ✅ All columns already exist - no migration needed")
            return True

        # Execute migrations
        for sql in migrations:
            cursor.execute(sql)
            print(f"   ✓ Executed: {sql[:80]}...")

        # Update existing rows based on current status
        print("   Updating existing download states...")

        # For downloads with status='ready', mark all components as completed
        cursor.execute("""
            UPDATE download_state
            SET video_status = 'completed',
                subtitle_status = 'completed',
                translation_status = 'completed'
            WHERE status = 'ready'
        """)
        ready_count = cursor.rowcount

        # For downloads with status='downloading', determine component status from progress
        cursor.execute("""
            UPDATE download_state
            SET video_status = CASE
                    WHEN video_progress >= 100.0 THEN 'completed'
                    WHEN video_progress > 0.0 THEN 'downloading'
                    ELSE 'pending'
                END,
                subtitle_status = CASE
                    WHEN subtitle_progress >= 100.0 THEN 'completed'
                    WHEN subtitle_progress > 0.0 THEN 'downloading'
                    ELSE 'pending'
                END,
                translation_status = CASE
                    WHEN translation_progress >= 100.0 THEN 'completed'
                    WHEN translation_progress > 0.0 THEN 'translating'
                    ELSE 'pending'
                END
            WHERE status = 'downloading'
        """)
        downloading_count = cursor.rowcount

        # For failed downloads, mark video as failed (conservative approach)
        cursor.execute("""
            UPDATE download_state
            SET video_status = 'failed',
                subtitle_status = 'pending',
                translation_status = 'pending'
            WHERE status IN ('failed', 'translation_failed')
        """)
        failed_count = cursor.rowcount

        # For available downloads, all components are pending
        cursor.execute("""
            UPDATE download_state
            SET video_status = 'pending',
                subtitle_status = 'pending',
                translation_status = 'pending'
            WHERE status = 'available'
        """)
        available_count = cursor.rowcount

        conn.commit()

        print(f"   ✅ Migration complete!")
        print(f"      Updated {ready_count} ready downloads")
        print(f"      Updated {downloading_count} downloading downloads")
        print(f"      Updated {failed_count} failed downloads")
        print(f"      Updated {available_count} available downloads")

        return True

    except Exception as e:
        conn.rollback()
        print(f"   ❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DATABASE_FILE
    success = migrate_download_state(db_path)
    sys.exit(0 if success else 1)
