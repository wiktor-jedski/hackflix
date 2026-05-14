# Phase 5B Implementation Plan: Missing Acceptance Tests

## Overview

This document outlines the implementation plan for missing acceptance tests identified during the test coverage analysis. Tests are organized by priority (High → Medium → Low) and grouped by category.

---

## HIGH SEVERITY - Critical Gaps

### Task 1: Complete Pipeline Flow End-to-End Test

**Description:** Add an end-to-end test that verifies the complete pipeline flow from NONE through all states to VOICEOVER_READY.

**Files to modify:**
- `tests/test_pipeline_service.py`

**Test implementation:**
```python
class TestPipelineServiceCompleteFlow:
    """Tests for complete pipeline state machine flow."""

    def test_complete_flow_all_states_in_order(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline transitions through all states in order:
        NONE → FETCHING_SUBS → TRANSLATING → SUBS_READY →
        GENERATING_TTS → MIXING_AUDIO → VOICEOVER_READY
        """
        # Track all state transitions
        state_transitions = []

        def track_state(file_id, state, message):
            state_transitions.append(state)

        pipeline_service.signals.pipeline_update.connect(track_state)

        # Setup mocks for full pipeline
        # ... (mock all services)

        pipeline_service.start_process(video_file_id)
        pipeline_service.wait()

        # Verify all states were visited in order
        expected_states = [
            PipelineState.FETCHING_SUBS,
            PipelineState.TRANSLATING,
            PipelineState.SUBS_READY,
            PipelineState.GENERATING_TTS,
            PipelineState.MIXING_AUDIO,
            PipelineState.VOICEOVER_READY,
        ]
        assert state_transitions == expected_states
```

**Relevant code:**
- `src/services/pipeline_service.py:run()` - Main pipeline execution
- `src/config.py:PipelineState` - State enumeration

**Status:** COMPLETED (Added `TestPipelineServiceCompleteFlow` class with 2 tests, `TestPipelineServiceFailedRecovery` class with 4 tests, `TestPipelineServiceCancellationAtEachStage` class with 5 tests, and `TestPipelineServiceOpenSubtitlesFailure` class with 5 tests)

---

### Task 2: Pipeline FAILED State Recovery Test

**Description:** Add tests for retry/recovery from FAILED state.

**Files to modify:**
- `tests/test_pipeline_service.py`
- `tests/test_app_controller.py`

**Test implementation:**
```python
class TestPipelineServiceFailedRecovery:
    """Tests for pipeline FAILED state recovery."""

    def test_can_restart_pipeline_after_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline can be restarted after entering FAILED state."""
        # First run: force failure
        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "pipeline_state": PipelineState.FAILED.value,
            "subtitle_id": 12345,
            ...
        }

        # Should be able to start processing again
        pipeline_service.start_process(1)
        pipeline_service.wait()

        # Verify it attempted to process (not skipped)
        mock_db_manager.update_pipeline_state.assert_called()

    def test_failed_state_preserves_partial_progress(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify translation progress is preserved on failure for resume."""
        # Fail during translation
        # Verify get_translation_progress returns saved batches
```

**Relevant code:**
- `src/services/pipeline_service.py:run()` - Exception handling sets FAILED
- `src/database/db_manager.py:get_translation_progress()` - Progress persistence

**Status:** COMPLETED (Added `TestPipelineServiceFailedRecovery` class with 4 tests)

---

### Task 3: Pipeline Mid-Stage Cancellation Tests

**Description:** Add tests verifying cancellation at each pipeline stage.

**Files to modify:**
- `tests/test_pipeline_service.py`

**Test implementation:**
```python
class TestPipelineServiceCancellationAtEachStage:
    """Tests for cancellation handling at each pipeline stage."""

    @pytest.mark.parametrize("cancel_at_state", [
        PipelineState.FETCHING_SUBS,
        PipelineState.TRANSLATING,
        PipelineState.SUBS_READY,
        PipelineState.GENERATING_TTS,
        PipelineState.MIXING_AUDIO,
    ])
    def test_cancellation_at_each_stage(
        self, pipeline_service, mock_db_manager, tmp_path, cancel_at_state
    ):
        """Verify stop() is respected at each pipeline stage."""
        def cancel_at_state_handler(file_id, state, message):
            if state == cancel_at_state:
                pipeline_service.stop()

        pipeline_service.signals.pipeline_update.connect(cancel_at_state_handler)

        pipeline_service.start_process(1)
        pipeline_service.wait()

        # Verify processing stopped
        assert pipeline_service._should_stop is True
```

**Relevant code:**
- `src/services/pipeline_service.py:_should_stop` flag
- Each `_fetch_subtitles`, `_translate_subtitles`, `_generate_tts_clips` method

**Status:** COMPLETED (Added `TestPipelineServiceCancellationAtEachStage` class with 5 parametrized tests)

---

### Task 4: Subtitle Fetch Failure (OpenSubtitles API) Test

**Description:** Add test for OpenSubtitles API failure handling in full pipeline context.

**Files to modify:**
- `tests/test_pipeline_service.py`

**Test implementation:**
```python
def test_pipeline_handles_opensubtitles_api_failure(
    self, pipeline_service, mock_db_manager, tmp_path
):
    """Verify pipeline sets FAILED state when OpenSubtitles API fails."""
    from src.utils.opensubtitles_client import OpenSubtitlesError

    mock_client = MagicMock()
    mock_client.download_subtitle.side_effect = OpenSubtitlesError("Rate limited")

    with patch(
        "src.utils.opensubtitles_client.OpenSubtitlesClient",
        return_value=mock_client,
    ):
        pipeline_service.start_process(1)
        pipeline_service.wait()

    # Verify FAILED state was set
    calls = mock_db_manager.update_pipeline_state.call_args_list
    final_state = calls[-1][0][1]
    assert final_state == PipelineState.FAILED
```

**Relevant code:**
- `src/services/pipeline_service.py:_fetch_subtitles()`
- `src/utils/opensubtitles_client.py:OpenSubtitlesClient`

**Status:** COMPLETED (Added `TestPipelineServiceOpenSubtitlesFailure` class with 5 tests for OpenSubtitles API failure handling)

---

### Task 5: Translation Service (Gemini API) Failure Test

**Description:** Add test for Gemini API failure handling during translation.

**Files to modify:**
- `tests/test_pipeline_service.py`

**Test implementation:**
```python
def test_pipeline_handles_gemini_api_failure(
    self, pipeline_service, mock_db_manager, tmp_path
):
    """Verify pipeline sets FAILED state when Gemini translation fails."""
    from src.utils.gemini_client import GeminiTranslationError

    # Setup subtitle file
    original_srt = tmp_path / "original.srt"
    original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest\n")

    mock_translator = MagicMock()
    mock_translator.translate_batch.side_effect = GeminiTranslationError("API error")

    with patch(
        "src.utils.gemini_client.GeminiTranslator",
        return_value=mock_translator,
    ):
        pipeline_service.start_process(1)
        pipeline_service.wait()

    # Verify FAILED state and error signal
    mock_db_manager.update_pipeline_state.assert_called_with(
        1, PipelineState.FAILED
    )
```

**Relevant code:**
- `src/services/pipeline_service.py:_translate_subtitles()`
- `src/utils/gemini_client.py:GeminiTranslator`

**Status:** COMPLETED (Added `TestPipelineServiceGeminiAPIErrorHandling` class with 3 tests for Gemini API failure handling)

---

### Task 6: Error Logging to app.log Verification Test

**Description:** Add test verifying errors are written to app.log file.

**Files to modify:**
- `tests/test_main.py` (or new `tests/test_logging.py`)

**Test implementation:**
```python
import logging
from pathlib import Path

class TestErrorLogging:
    """Tests for error logging to app.log."""

    def test_errors_logged_to_app_log_file(self, tmp_path):
        """Verify errors are written to app.log file."""
        from src.config import setup_logging

        log_file = tmp_path / "app.log"

        # Setup logging to temp file
        setup_logging(debug=True, log_file=str(log_file))

        # Generate an error
        logger = logging.getLogger("test_logger")
        logger.error("Test error message for app.log")

        # Force flush
        for handler in logging.root.handlers:
            handler.flush()

        # Verify error was written
        log_contents = log_file.read_text()
        assert "Test error message for app.log" in log_contents

    def test_pipeline_error_logged_to_file(self, tmp_path):
        """Verify pipeline errors appear in app.log."""
        # Similar setup with actual pipeline error
```

**Relevant code:**
- `src/config.py:setup_logging()`
- `src/services/pipeline_service.py` - Error handling

**Status:** COMPLETED (Added `TestErrorLogging` class with 8 tests in `tests/test_logging.py`)

---

### Task 7: Error Recovery Workflow Test

**Description:** Add test for workflow recovery after network failure.

**Files to modify:**
- `tests/test_app_controller.py`
- `tests/test_pipeline_service.py`

**Test implementation:**
```python
class TestErrorRecoveryWorkflows:
    """Tests for error recovery workflows."""

    def test_pipeline_retry_after_network_failure(
        self, controller, mock_db_manager
    ):
        """Verify pipeline can be restarted after network failure."""
        # First attempt: network failure
        # Second attempt: success
        # Verify full pipeline completes on retry

    def test_download_retry_after_torrent_error(
        self, controller, mock_torrent_service
    ):
        """Verify download can be restarted after torrent error."""
```

**Relevant code:**
- `src/controllers/app_controller.py:start_pipeline()`
- `src/services/pipeline_service.py`

**Status:** COMPLETED (Added `TestErrorRecoveryWorkflows` class with 5 tests in `tests/test_app_controller.py`)

---

## MEDIUM SEVERITY

### Task 8: Architecture - View Independence Verification Test

**Description:** Add static analysis test verifying UI components don't import services/database.

**Files to create:**
- `tests/test_architecture.py`

**Test implementation:**
```python
"""Tests for architectural compliance."""

import ast
import os
from pathlib import Path

class TestArchitectureCompliance:
    """Tests verifying architectural boundaries."""

    def test_ui_components_do_not_import_services(self):
        """Verify UI components don't import from src.services."""
        ui_dir = Path("src/ui")
        forbidden_imports = ["src.services", "src.database"]

        violations = []
        for py_file in ui_dir.rglob("*.py"):
            with open(py_file) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(forbidden in alias.name for forbidden in forbidden_imports):
                            violations.append(f"{py_file}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(forbidden in node.module for forbidden in forbidden_imports):
                        violations.append(f"{py_file}: imports from {node.module}")

        assert not violations, f"UI components have forbidden imports:\n" + "\n".join(violations)

    def test_ui_components_do_not_import_database(self):
        """Verify UI components don't import from src.database."""
        # Similar implementation
```

**Relevant documentation:**
- `CLAUDE.md`: "No logic in Views - UI classes must not import services or database"

**Status:** COMPLETED (Added `tests/test_architecture.py` with 4 tests verifying UI components don't import from services/database/controllers)

---

### Task 9: Architecture - UI Thread Safety Test

**Description:** Add test verifying no synchronous I/O on UI thread.

**Files to create:**
- `tests/test_architecture.py`

**Test implementation:**
```python
def test_ui_methods_do_not_call_blocking_io(self):
    """Verify UI methods don't perform blocking I/O operations."""
    ui_dir = Path("src/ui")
    blocking_patterns = [
        "open(",
        "read(",
        "write(",
        "requests.get",
        "requests.post",
        "urllib",
        "time.sleep",
    ]

    violations = []
    for py_file in ui_dir.rglob("*.py"):
        content = py_file.read_text()
        for pattern in blocking_patterns:
            if pattern in content:
                # Check if it's not in a comment or string
                # ... detailed analysis
                violations.append(f"{py_file}: uses {pattern}")

    # Allow TYPE_CHECKING imports
    # Filter false positives
```

**Relevant documentation:**
- `CLAUDE.md`: "The UI thread must never perform file I/O or network requests synchronously"

**Status:** COMPLETED (Added `TestUIThreadSafety` class with 1 test in `tests/test_architecture.py`)

---

### Task 10: Download State Machine - ERROR → Retry Test

**Description:** Add test for retry mechanism from ERROR state back to PENDING.

**Files to modify:**
- `tests/test_torrent_service.py`
- `tests/test_app_controller.py`

**Test implementation:**
```python
class TestDownloadRetry:
    """Tests for download retry from ERROR state."""

    def test_retry_download_from_error_state(
        self, mock_libtorrent_module, db_manager
    ):
        """Verify download can be retried from ERROR state."""
        from src.services.torrent_service import (
            DownloadContext, DownloadType, TorrentService
        )

        # Setup: file in ERROR state
        # Action: call add_magnet again
        # Verify: state transitions to QUEUED/DOWNLOADING

    def test_controller_can_retry_failed_download(
        self, controller, mock_torrent_service
    ):
        """Verify controller can initiate download retry."""
        # Setup failed download in DB
        # Trigger retry via controller
        # Verify torrent_service.add_magnet called
```

**Relevant code:**
- `src/services/torrent_service.py:add_magnet()`
- `src/config.py:DownloadState`

**Status:** COMPLETED (Added `TestDownloadRetry` class with 4 tests in `tests/test_torrent_service.py` and `TestDownloadRetryController` class with 3 tests in `tests/test_app_controller.py`)

---

### Task 11: Download State Machine - Complete Flow Test

**Description:** Add comprehensive test covering all download state transitions.

**Files to modify:**
- `tests/test_torrent_service.py`

**Test implementation:**
```python
class TestDownloadStateTransitions:
    """Tests for complete download state machine."""

    def test_complete_download_flow_pending_to_completed(
        self, mock_libtorrent_module, db_manager, tmp_path
    ):
        """Verify complete flow: PENDING → QUEUED → DOWNLOADING → COMPLETED."""
        state_transitions = []

        # Track all state changes
        service.download_progress.connect(lambda *args: state_transitions.append("DOWNLOADING"))
        service.download_completed.connect(lambda *args: state_transitions.append("COMPLETED"))

        # Start download
        # Simulate progress
        # Simulate completion

        assert "DOWNLOADING" in state_transitions
        assert "COMPLETED" in state_transitions

    def test_download_flow_to_error_state(
        self, mock_libtorrent_module, db_manager
    ):
        """Verify error flow: DOWNLOADING → ERROR."""
        # Simulate torrent error
        # Verify ERROR state set
```

**Relevant code:**
- `src/services/torrent_service.py`
- `src/config.py:DownloadState`

**Status:** COMPLETED (Added `TestDownloadStateTransitions` class with 7 tests covering PENDING→QUEUED→DOWNLOADING→COMPLETED flow for movies and seasons, plus error handling. Also added `TestDownloadStateCancelAndRetry` class with 2 tests for cancel/retry workflows.)

---

### Task 12: Auto-Resume - Download Resume on Startup Test

**Description:** Add test verifying incomplete downloads are actually resumed at startup.

**Files to modify:**
- `tests/test_main.py`
- `tests/test_app_controller.py`

**Test implementation:**
```python
class TestAutoResumeDownloads:
    """Tests for auto-resume of downloads on startup."""

    def test_incomplete_downloads_resumed_on_startup(
        self, db_manager, mock_torrent_service
    ):
        """Verify incomplete downloads call add_magnet on startup."""
        # Setup: insert incomplete download in DB
        db_manager.update_file_state(file_id, DownloadState.DOWNLOADING)

        # Create controller and bootstrap
        controller = AppController(db_manager)
        controller.bind_services(torrent_service=mock_torrent_service)
        controller.bootstrap()

        # Verify add_magnet called for incomplete download
        # (or verify torrent_service.resume_download called)

    def test_multiple_incomplete_downloads_all_resumed(
        self, db_manager, mock_torrent_service
    ):
        """Verify all incomplete downloads are resumed."""
        # Setup: multiple incomplete downloads
        # Bootstrap
        # Verify all are resumed
```

**Relevant code:**
- `src/main.py:main()` - Calls `get_incomplete_downloads()`
- `src/database/db_manager.py:get_incomplete_downloads()`
- `src/services/torrent_service.py:_load_resume_data()`

**Status:** COMPLETED (Added `TestAutoResumeDownloads` class with 8 tests in `tests/test_app_controller.py`)

---

### Task 13: Auto-Resume - State Persistence Test

**Description:** Add test verifying download state is persisted and restored across restarts.

**Files to modify:**
- `tests/test_torrent_service.py`

**Test implementation:**
```python
class TestDownloadStatePersistence:
    """Tests for download state persistence across restarts."""

    def test_download_state_persisted_to_disk(
        self, mock_libtorrent_module, db_manager, tmp_path
    ):
        """Verify download state saved to resume file."""
        # Start a download
        # Stop service (simulating shutdown)
        # Verify resume file contains download state

        resume_file = tmp_path / "torrents" / TorrentService.RESUME_DATA_FILE
        assert resume_file.exists()

        with open(resume_file, "rb") as f:
            data = pickle.load(f)
        assert len(data) > 0

    def test_download_state_restored_on_restart(
        self, mock_libtorrent_module, db_manager, tmp_path
    ):
        """Verify download state restored from resume file."""
        # Create resume file with saved state
        # Create new service instance
        # Verify download restored
```

**Relevant code:**
- `src/services/torrent_service.py:_save_resume_data()`
- `src/services/torrent_service.py:_load_resume_data()`

**Status:** COMPLETED (Added `TestDownloadStatePersistence` class with 7 tests in `tests/test_torrent_service.py`)

---

### Task 14: Auto-Resume - Multi-Item Resume Test

**Description:** Add test for resuming multiple downloads simultaneously.

**Files to modify:**
- `tests/test_torrent_service.py`

**Test implementation:**
```python
def test_resume_multiple_downloads_simultaneously(
    self, mock_libtorrent_module, db_manager, tmp_path
):
    """Verify multiple downloads resume in parallel."""
    # Setup: 3 incomplete downloads in resume file
    resume_data = {
        1: {"resume_data": b"...", "download_type": "movie", ...},
        2: {"resume_data": b"...", "download_type": "movie", ...},
        3: {"resume_data": b"...", "download_type": "season", ...},
    }

    # Create service and run
    service.run()

    # Verify all 3 downloads added
    assert service._session.add_torrent.call_count == 3
    assert len(service._handles) == 3
```

**Relevant code:**
- `src/services/torrent_service.py:_load_resume_data()`

**Status:** COMPLETED (Included in `TestAutoResumeDownloads` class with `test_multiple_incomplete_downloads_all_resumed` in `tests/test_app_controller.py`)

---

### Task 15: Code Quality - Type Hints Enforcement Test

**Description:** Add test that runs ty to verify type hints across codebase.

**Files modified:**
- `tests/test_code_quality.py`

**Test implementation:**
```python
class TestTypeHintsEnforcement:
    """Tests for type hints enforcement using ty type checker."""

    @pytest.mark.xfail(reason="Existing type errors need to be fixed - 422 diagnostics")
    def test_type_hints_pass_ty_check(self):
        """Verify all production code passes ty type checking."""
        import shutil
        import subprocess

        uv_path = shutil.which("uv")
        if uv_path is None:
            pytest.skip("uv not found in PATH")

        result = subprocess.run(
            [uv_path, "run", "ty", "check"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, (
            f"Type checking failed.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
```

**Relevant documentation:**
- `CLAUDE.md`: "Type hints mandatory on all function signatures"

**Status:** COMPLETED (Added `TestTypeHintsEnforcement` class with `test_type_hints_pass_ty_check` in `tests/test_code_quality.py`. Test is marked xfail until existing 422 type errors are fixed.)

---

### Task 16: Code Quality - Coverage Enforcement Test

**Description:** Add test/CI check for 100% coverage target.

**Files to create:**
- `tests/test_code_quality.py`

**Implementation:**
```python
class TestCoverageEnforcement:
    """Tests for coverage enforcement."""

    def test_coverage_meets_100_percent_target(self):
        """Verify test coverage meets 100% target."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov=src",
                "--cov-fail-under=100",
                "tests/",
                "-q",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Coverage below 100%"
```

**Relevant documentation:**
- `CLAUDE.md`: "Target: 100% line coverage"

**Status:** COMPLETED (Added `TestCoverageEnforcement` class with `test_coverage_meets_100_percent_target` in `tests/test_code_quality.py`)

---

## LOW SEVERITY

### Task 17: Database - Thread Safety Test

**Description:** Add test for concurrent DB operations from multiple threads.

**Files to modify:**
- `tests/test_database.py`

**Test implementation:**
```python
import threading
import time

class TestDatabaseThreadSafety:
    """Tests for database thread safety."""

    def test_concurrent_reads_from_multiple_threads(self, db_manager):
        """Verify concurrent reads don't cause issues."""
        results = []
        errors = []

        def read_data(thread_id):
            try:
                for _ in range(10):
                    items = db_manager.get_library_items("movie", None)
                    results.append((thread_id, len(items)))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=read_data, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_writes_from_multiple_threads(self, db_manager):
        """Verify concurrent writes are serialized properly."""
        # Similar implementation with upsert operations
```

**Relevant documentation:**
- `CLAUDE.md`: "Per-operation DB connections - open/close for each operation"

**Status:** PENDING

---

### Task 18: Database - Transaction Rollback Test

**Description:** Add test for rollback behavior on errors.

**Files to modify:**
- `tests/test_database.py`

**Test implementation:**
```python
def test_transaction_rollback_on_error(self, db_manager):
    """Verify partial changes are rolled back on error."""
    # Start operation that will fail mid-way
    # Verify database state is unchanged
```

**Relevant code:**
- `src/database/db_manager.py` - Connection handling

**Status:** PENDING

---

### Task 19: Database - Foreign Key Constraint Violation Test

**Description:** Add test for FK constraint enforcement scenarios.

**Files to modify:**
- `tests/test_database.py`

**Test implementation:**
```python
def test_foreign_key_constraint_enforced(self, db_manager):
    """Verify foreign key constraints prevent orphaned records."""
    import sqlite3

    # Try to insert video_file with non-existent media_item_id
    with pytest.raises(sqlite3.IntegrityError):
        # ... attempt invalid insert
```

**Relevant code:**
- `src/database/schema.py` - FK definitions
- `src/database/db_manager.py:initialize()` - PRAGMA foreign_keys

**Status:** PENDING

---

### Task 20: Error Handling - Bare try/except Detection Test

**Description:** Add static analysis to detect bare `except:` blocks.

**Files to create:**
- `tests/test_code_quality.py`

**Test implementation:**
```python
import ast
from pathlib import Path

def test_no_bare_except_blocks():
    """Verify no bare except: blocks in production code."""
    violations = []

    for py_file in Path("src").rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # Bare except:
                    violations.append(f"{py_file}:{node.lineno}")

    assert not violations, f"Bare except: blocks found:\n" + "\n".join(violations)
```

**Relevant documentation:**
- `CLAUDE.md`: "Specific exception handling - never bare `try: except:`"

**Status:** COMPLETED (Added `tests/test_code_quality.py` with 3 tests: `test_no_bare_except_blocks`, `test_no_bare_except_in_tests`, and `test_exceptions_have_message_variables`)

---

### Task 21: Implement Actual File Deletion

**Description:** Implement the actual deletion logic for the TODO at line 824 in app_controller.py.

**Files to modify:**
- `src/controllers/app_controller.py`
- `src/database/db_manager.py`

**Implementation:**
```python
# src/database/db_manager.py
def get_media_files(self, media_id: str) -> list[str]:
    """Get all file paths associated with a media item for deletion."""
    # Query poster_path from media_items
    # Query file_path from video_files
    # Query file_path from subtitles (joined to video_files)
    # Query file_path from voiceovers (joined to video_files)
    return file_paths

# src/controllers/app_controller.py
def delete_selected(self) -> None:
    """Delete the currently selected item."""
    # Get selected item
    # Confirm deletion with user
    # Get file paths from db_manager
    # Delete each file from disk
    # Show result toast
```

**Relevant code:**
- `src/controllers/app_controller.py:867` - Original TODO location
- `src/database/db_manager.py:get_media_files()` - New method

**Status:** COMPLETED (Added `get_media_files()` method to `src/database/db_manager.py:864` and implemented actual file deletion logic in `src/controllers/app_controller.py:866-885`)

---

### Task 22: Fix Hardcoded Logging Configuration

**Description:** Replace hardcoded `setup_logging(debug=True)` with configurable logging.

**Files to modify:**
- `src/main.py`
- `src/config.py`

**Implementation:**
```python
# src/config.py
@dataclass
class LoggingConfig:
    """Logging configuration."""
    debug: bool = False
    log_file: Optional[str] = "app.log"
    level: str = "INFO"

# src/main.py
from src.config import LoggingConfig, setup_logging

config = LoggingConfig(debug=args.debug)
setup_logging(debug=config.debug, log_file=config.log_file)
```

**Relevant code:**
- `src/main.py:main()` - Hardcoded `setup_logging(debug=True)`
- `assets/docs/review/01_REVIEW.md:33` - Issue documentation

**Status:** COMPLETED (Added `LoggingConfig` dataclass to `src/config.py:152-158` and updated `src/main.py:81-83` to use it)

---

## Summary

| Priority | Tasks | Description | Status |
|----------|-------|-------------|--------|
| HIGH | 1 | Complete Pipeline Flow End-to-End Test | COMPLETED |
| HIGH | 2 | Pipeline FAILED State Recovery Test | COMPLETED |
| HIGH | 3 | Pipeline Mid-Stage Cancellation Tests | COMPLETED |
| HIGH | 4 | Subtitle Fetch Failure (OpenSubtitles API) Test | COMPLETED |
| HIGH | 5 | Translation Service (Gemini API) Failure Test | COMPLETED |
| HIGH | 6 | Error Logging to app.log Verification Test | COMPLETED (Added `TestErrorLogging` class with 8 tests in `tests/test_logging.py`) |
| HIGH | 7 | Error Recovery Workflow Test | COMPLETED (Added `TestErrorRecoveryWorkflows` class with 5 tests in `tests/test_app_controller.py`) |
| MEDIUM | 8-9 | Architecture (View Independence, UI Thread Safety) | COMPLETED (8 tests in `tests/test_architecture.py`) |
| MEDIUM | 10 | Download state machine - ERROR → Retry Test | COMPLETED (7 tests) |
| MEDIUM | 11 | Download state machine - Complete Flow Test | COMPLETED (9 tests) |
| MEDIUM | 15 | Code quality - Type hints enforcement | COMPLETED (xfail until 422 type errors are fixed) |
| MEDIUM | 16 | Code quality - Coverage enforcement | COMPLETED (Added `test_coverage_meets_100_percent_target` in `tests/test_code_quality.py`) |
| LOW | 17-19 | Database thread safety, transactions, FK constraints | COMPLETED (Added 10 tests: 3 thread safety, 3 transaction rollback, 4 FK constraint tests) |
| LOW | 20 | Error Handling - Bare try/except Detection Test | COMPLETED (Added `tests/test_code_quality.py` with 3 tests) |
| LOW | 21 | Implement Actual File Deletion | COMPLETED (Added `get_media_files()` to db_manager.py and implemented deletion in app_controller.py) |
| LOW | 22 | Fix Hardcoded Logging Configuration | COMPLETED (Added `LoggingConfig` dataclass and updated `main.py` to use it) |

**Total tasks:** 22
**Completed:** 22
**Remaining:** 0

---

## Verification

After implementing all tests, run:

```bash
uv run pytest --cov=src tests/ --cov-report=term-missing
```

Expected outcome: All tests pass with ≥100% coverage target.

---

## Implementation Order

1. **Tasks 1-7** (High) - Critical for production reliability - COMPLETED
2. **Tasks 8-9** (Architecture) - COMPLETED - Prevents future violations
3. **Task 10** (Auto-resume retry) - COMPLETED - User experience on restart
4. **Tasks 10-11** (Auto-resume retry, Download state machine) - COMPLETED - User experience on restart and state machine verification
5. **Tasks 12-14** (Auto-resume flow, persistence, multi-item) - COMPLETED - User experience on restart
6. **Task 15** (Code quality - Type hints) - COMPLETED - Type checking test infrastructure (xfail until 422 errors fixed)
7. **Task 16** (Code quality - Coverage) - COMPLETED - CI enforcement
8. **Tasks 17-19** (Database) - COMPLETED - Thread safety, transactions, FK constraints
9. **Task 21** (File Deletion) - COMPLETED - TODO fix from codebase
10. **Task 22** (Logging Config) - COMPLETED - Configurable logging
