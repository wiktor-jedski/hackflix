  Final Implementation Plan: Phase 5 Voiceover Pipeline Fixes

## Progress: ALL TASKS COMPLETED ✓

Task 1: Instantiate PipelineService in main.py
File: src/main.py
Changes:
1. Add import: from src.services.pipeline_service import PipelineService
2. Instantiate: pipeline_service = PipelineService(db_manager=db_manager)
3. Pass to controller.bind_services(pipeline_service=pipeline_service)
Status: COMPLETED ✓
---
Task 2: Refactor PipelineService to use QThread
Files: src/services/pipeline_service.py, src/controllers/app_controller.py
Changes:
PipelineService changes:
1. Change inheritance from QRunnable to QThread ✓
2. Add self.start() in start_process() method instead of setting flags ✓
3. Remove run() method - logic stays in start_process() or move to run() and call self.exec_() ✓
4. Remove _is_busy flag - use isRunning() instead ✓
AppController changes:
1. Add import: from PyQt5.QtCore import QThreadPool
2. Add in __init__: self._thread_pool = QThreadPool()
3. Simplify start_pipeline() - just call start_process() (thread starts automatically)
Status: COMPLETED ✓
Tests Updated: 48/48 passing, fixture added for thread cleanup
---
Task 3: Make rate-limit sleep interruptible
File: src/utils/gemini_client.py
Change: Replace blocking time.sleep(60) with interruptible loop:
for _ in range(60):
    if hasattr(self, '_should_stop') and self._should_stop:
        raise GeminiTranslationError("Cancelled")
    time.sleep(1)
Status: COMPLETED ✓
---
Task 4: Optimize stretch_audio for identity factor
File: src/utils/audio_processor.py
Change: Add early return with file copy when speedup_factor == 1.0:
if speedup_factor == 1.0:
    import shutil
    shutil.copy(str(audio_path), str(output_path))
    logger.info("No stretching needed, copied audio to %s", output_path)
    return
Status: COMPLETED ✓
---
Task 2: Refactor PipelineService to use QThread
Files: src/services/pipeline_service.py, src/controllers/app_controller.py
Changes:
PipelineService changes:
1. Change inheritance from QRunnable to QThread ✓
2. Add self.start() in start_process() method instead of setting flags ✓
3. Remove run() method - logic stays in start_process() or move to run() and call self.exec_() ✓
4. Remove _is_busy flag - use isRunning() instead ✓
AppController changes:
1. Add import: from PyQt5.QtCore import QThreadPool
2. Add in __init__: self._thread_pool = QThreadPool()
3. Simplify start_pipeline() - just call start_process() (thread starts automatically)
Status: COMPLETED ✓
Tests Updated: 48/48 passing, fixture added for thread cleanup
---
Task 3: Make rate-limit sleep interruptible
File: src/utils/gemini_client.py
Change: Replace blocking time.sleep(60) with interruptible loop:
for _ in range(60):
    if hasattr(self, '_should_stop') and self._should_stop:
        raise GeminiTranslationError("Cancelled")
    time.sleep(1)
Status: COMPLETED ✓
---

Task 4: Optimize stretch_audio for identity factor
File: src/utils/audio_processor.py
Change: Add early return with file copy when speedup_factor == 1.0:
if speedup_factor == 1.0:
    import shutil
    shutil.copy(str(audio_path), str(output_path))
    logger.info("No stretching needed, copied audio to %s", output_path)
    return
Status: COMPLETED ✓
---
## Verification
After implementation, run:
uv run pytest --cov=src tests/ --cov-report=term-missing

Current Status: 831 tests passing (96% coverage)
---

## Summary
All Tasks Completed:
- Task 1: PipelineService now instantiated in main.py and passed to controller
- Task 2: PipelineService runs in a background thread using QThread
- Task 3: Rate-limit sleep is now interruptible via _should_stop flag
- Task 4: Optimized stretch_audio - copies file directly when speedup_factor == 1.0
- Removed _is_busy flag, uses isRunning() instead
- Updated all pipeline service tests to work with QThread model
- Added thread cleanup fixture to prevent hanging threads during tests
- Updated stretch_audio test to verify copy behavior for identity factor
---
