#!/usr/bin/env python3
"""
Detect completed downloads and update database.

Scans the download directory for completed video files and updates
the download_state table accordingly.
"""

import os
import sqlite3
from pathlib import Path


def detect_completed_downloads(db_path='hackflix.db', download_dir='~/Videos/HackFlix'):
    """Detect and mark completed downloads"""
    download_dir = os.path.expanduser(download_dir)

    if not os.path.exists(download_dir):
        print(f"Download directory doesn't exist: {download_dir}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all movies in 'downloading' state
    cursor.execute("""
        SELECT ds.id, m.title, ds.progress, ds.phase
        FROM download_state ds
        JOIN movies m ON ds.id = m.id
        WHERE ds.status = 'downloading'
    """)

    downloading = cursor.fetchall()

    print(f"\nScanning {download_dir} for completed downloads...\n")
    print(f"Found {len(downloading)} items in 'downloading' state:\n")

    video_extensions = ('.mp4', '.mkv', '.avi', '.mov')

    for row in downloading:
        item_id = row['id']
        title = row['title']

        print(f"Checking: {title} ({item_id})")

        # Search for video files matching this title
        found_video = None
        video_size = 0

        for root, dirs, files in os.walk(download_dir):
            for file in files:
                if file.lower().endswith(video_extensions):
                    # Check if title is in the folder name or file name
                    if title.lower() in root.lower() or title.lower() in file.lower():
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)

                        # Consider files > 100MB as complete movies
                        if file_size > 100 * 1024 * 1024:
                            found_video = file_path
                            video_size = file_size
                            break
            if found_video:
                break

        if found_video:
            size_gb = video_size / (1024 ** 3)
            print(f"  ✅ Found complete video: {os.path.basename(found_video)}")
            print(f"     Size: {size_gb:.2f} GB")
            print(f"     Path: {found_video}")

            # Update database to mark as complete
            cursor.execute("""
                UPDATE download_state
                SET status = 'ready',
                    progress = 100.0,
                    phase = NULL,
                    phase_progress = 100.0,
                    video_progress = 100.0,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (item_id,))

            print(f"     Updated status to 'ready'\n")
        else:
            print(f"  ⏳ No complete video found (still downloading or missing)\n")

    conn.commit()
    conn.close()

    print("✅ Scan complete!")


if __name__ == '__main__':
    detect_completed_downloads()
