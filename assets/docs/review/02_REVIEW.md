# Phase 2 Code review

1.  **TorrentService - Season Pack Architecture Violation:**
    The current implementation of `TorrentService` maps one `magnet` to one `video_file_id`. This works for Movies but fails for Series (Season Packs).
    *   **The Issue:** A Season Pack magnet corresponds to a `season_id` but contains multiple `video_files` (episodes). `_on_download_complete` currently only finds the single largest file and updates one DB record.
    *   **Required Fix:**
        *   Modify `add_magnet` to accept a `download_context` (e.g., `{'type': 'movie', 'id': 1}` or `{'type': 'season', 'id': 5}`).
        *   Refactor `_on_download_complete` to handle multi-file matching.
        *   Implement a file-matcher that maps files within a torrent (e.g., `Series.S01E04.mkv`) to the specific Episode entries in the `video_files` table.

2.  **TorrentService - File Discovery Strategy:**
    `_find_largest_video` is insufficient.
    *   **Required Fix:** Replace with a strategy pattern.
        *   **Movie:** Find largest file with extension in `VIDEO_EXTENSIONS`.
        *   **Series:** Iterate `handle.get_torrent_info().files()` and match filenames against expected Episode numbers for that Season.

3.  **MetadataService - Testing Coverage:**
    Tests mock `db_manager` but do not validate data integrity for Series/Season structures.
    *   **Required Fix:** Add test cases in `test_metadata_service.py` that use a `content.json` fixture containing complex Series data. Verify that `upsert_content` is called with the correctly parsed structure.
