# Phase 4 Implementation Plan

## Overview

Phase 4 implements the media playback functionality for Hackflix. This phase adds the PlayerService (VLC wrapper), PlayerView (full-screen UI), and integrates them into the existing state machine architecture. **Note: PipelineService is Phase 5, not Phase 4** per development standards.

## Implementation Tasks

### 1. PlayerService Implementation ✅ COMPLETED

**File**: `src/services/player_service.py` (CREATE)

**Specification**: Reference `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 2.3

**Tasks**:
- [x] Create PlayerService class inheriting from QObject with complete type hints
- [x] Implement VLC instance initialization with hardware acceleration for Pi 5
  - **Source**: `assets/docs/architecture/01_SYSTEM_ARCHITECTURE.md` section 3.2
- [x] Add `initialize(self, video_frame_id: int) -> None` method to bind VLC to QFrame widget
- [x] Implement `load_video(self, file_path: str, voiceover_path: str | None) -> None` with external audio track support
  - **Source**: `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 2.3
- [x] Add playback control methods with complete type hints:
  - `toggle_pause(self) -> None`
  - `seek(self, delta_ms: int) -> None`
  - `get_position_seconds(self) -> int`
  - `set_position_seconds(self, seconds: int) -> None`
- [x] Implement audio controls:
  - `volume_up(self) -> None`
  - `volume_down(self) -> None`
  - `toggle_mute(self) -> None`
  - `cycle_audio_track(self) -> None`
- [x] Add signal emissions with type hints:
  - `playback_finished = pyqtSignal()`
  - `time_changed = pyqtSignal(int, int)`  # current_ms, total_ms
  - `error_occurred = pyqtSignal(str)`
- [x] Implement `get_audio_tracks(self) -> list[dict]` method for audio track enumeration
- [x] Add specific error handling for `vlc.VLCException` with standard logging
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 3
- [x] Create comprehensive unit tests with VLC mocking (54 tests, 97% coverage)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.2

**Dependencies**:
- python-vlc (already in pyproject.toml)
- PyQt5.QtCore for QObject and signals

### 2. PlayerView Implementation ✅ COMPLETED

**File**: `src/ui/components/player_view.py` (CREATE)

**Specification**: Reference `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 3.3

**Tasks**:
- [x] Create PlayerView class inheriting from QWidget with complete type hints
- [x] Implement full-screen layout with black background
- [x] Add QFrame widget for VLC video output using winId() integration
  - **Source**: `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 3.3
- [x] Implement On-Screen Display (OSD) with minimal icons only
  - **Source**: `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 4.3
- [x] Add OSD components: pause icon, seek icons, volume icon, audio track indicator
- [x] Implement OSD fade-out after 3 seconds of inactivity using QTimer
- [x] Add mouse cursor hiding for full-screen experience
- [x] Implement keyboard input handling integration with InputManager
- [x] Add methods for showing/hiding specific OSD elements with type hints
- [x] Create audio track selection overlay for L key functionality
- [x] Add proper styling consistent with application theme
- [x] Create unit tests with widget mocking using pytest-qt (49 tests, 100% coverage)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.3

**Dependencies**:
- PyQt5.QtWidgets for QWidget and layout
- PyQt5.QtCore for QTimer (OSD fade)
- Integration with existing UI styles

### 3. AppController Player Integration ✅ COMPLETED

**File**: `src/controllers/app_controller.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 1.1

**Tasks**:
- [x] Complete PlayerActiveHandler implementation with type hints
- [x] Add handling for TOGGLE_PAUSE, SEEK_FORWARD, SEEK_BACKWARD actions
  - **Source**: `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 3.5
- [x] Add handling for VOLUME_UP, VOLUME_DOWN, TOGGLE_MUTE actions
- [x] Add handling for CYCLE_AUDIO action with track switching
- [x] Implement `play_media(self, file_id: int) -> None` method to prepare PlayerService
- [x] Add service binding methods for PlayerService with type hints
- [x] Implement player activation logic in `activate_selected()` method
- [x] Add proper state transition to PLAYER_ACTIVE when playing media
- [x] Implement resume position saving on player exit (ESC key)
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4 (resume_position_seconds)
- [x] Add signal connections for PlayerService events with type hints
- [x] Implement navigation context preservation for player exit
- [x] Add error handling for player initialization failures

**Integration Points**:
- Modified `bind_services()` method to accept PlayerService
- Added signal handlers: `_on_playback_finished()`, `_on_time_changed()`, `_on_player_error()`
- Added player control methods: `player_toggle_pause()`, `player_seek_forward()`, `player_seek_backward()`, `player_volume_up()`, `player_volume_down()`, `player_toggle_mute()`, `player_cycle_audio()`
- Updated tests with 106 tests passing

### 4. MainWindow Player Integration ✅ COMPLETED

**File**: `src/ui/windows/main_window.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 4.3

**Tasks**:
- [x] Add PlayerView instance to MainWindow layout
- [x] Implement view switching between LibraryView and PlayerView
- [x] Add `show_player(self) -> None` and `hide_player(self) -> None` methods
- [x] Integrate PlayerView with InputManager event routing
- [x] Add proper focus management for player state
- [x] Add `get_player_frame_id()` method for VLC binding
- [x] Add `player_view` property to access PlayerView component
- [x] Handle player view resizing in `resizeEvent()`
- [ ] Implement status bar updates for player state (time, progress) - deferred to polish phase
- [x] Add toast notification integration for player errors (via controller)

### 5. Database Player Support ✅ COMPLETED (already existed)

**File**: `src/database/db_manager.py` (ALREADY EXISTS)

**Specification**: Reference `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4

**Tasks**:
- [x] `update_resume_position(self, file_id: int, position_seconds: int) -> None` already exists
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4
- [x] `get_video_details(self, media_id: str) -> dict | None` already exists
- [x] `get_video_file(self, video_file_id: int) -> dict | None` already exists
- [x] `get_voiceover(self, video_file_id: int) -> dict | None` already exists
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.6

### 6. Configuration and Constants (PARTIAL)

**File**: `src/config.py` (MODIFY)

**Tasks**:
- [x] Add player configuration constants with type hints
  - `PLAYER_SEEK_SECONDS: int = 10`
  - `PLAYER_VOLUME_STEP: int = 5`
  - `PLAYER_TIME_UPDATE_INTERVAL_MS: int = 500`
  - Note: `OSD_FADE_TIMEOUT_MS: int = 3000` already existed
- [ ] Add audio track constants
- [ ] Add resume position tracking constants

### 7. Testing Implementation ✅ COMPLETED

**Files**: `tests/test_player_service.py`, `tests/test_player_view.py`, `tests/test_app_controller.py`

**Specification**: Reference `assets/docs/architecture/06_DEV_STANDARDS.md` section 4

**Tasks**:
- [x] Create `tests/test_player_service.py` with VLC mocking (54 tests, 97% coverage)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.2
- [x] Create `tests/test_player_view.py` with pytest-qt (49 tests, 100% coverage)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.3
- [x] Add player state tests to `tests/test_app_controller.py` (MODIFY)
  - Added tests for PlayerActiveHandler: toggle_pause, seek, volume, mute, cycle_audio
  - Updated tests for new player integration (106 tests passing)
- [x] Full test suite passes (634 tests, 98% coverage)
- [ ] Add integration tests for complete player workflow - deferred to integration testing phase
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 3.5

### 8. Error Handling and Recovery ✅ COMPLETED

**Tasks**:
- [x] Implement VLC dependency checking in main.py (MODIFY)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 6
  - Implemented in `check_dependencies()` function, fails fast with exit code 1 if VLC missing
- [x] Add proper error handling for VLC initialization failures (in PlayerService)
- [x] Implement file existence validation before playback (in PlayerService.load_video)
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 5.2
- [ ] Add storage space validation for media files - deferred to future enhancement
- [x] Implement proper cleanup of VLC resources (PlayerService.release method)

### 9. Input Manager Updates ✅ COMPLETED

**File**: `src/ui/input_manager.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 3.5

**Tasks**:
- [x] Verify player action mappings are complete (lines 170-177)
  - Space → TOGGLE_PAUSE, M → TOGGLE_MUTE, L → CYCLE_AUDIO
- [x] Add context-specific key routing for PLAYER_ACTIVE state
  - Implemented in `PlayerActiveHandler`: accepts both NAVIGATE_* and explicit player actions
  - Arrow keys emit navigation actions, but controller interprets them as seek/volume in player state
- [x] Ensure proper debouncing for player control keys
  - Space, M, L are in `_DEBOUNCED_KEYS` set to prevent double-triggers
  - Arrow keys allow repeat for smooth seek/volume adjustment

### 10. Documentation and Integration

**Tasks**:
- [ ] Update AGENTS.md with Phase 4 commands and testing requirements
- [ ] Add PlayerService documentation to code docstrings
- [ ] Update system architecture documentation with Phase 4 components
- [ ] Document player controls and keyboard shortcuts
- [ ] Add VLC dependency notes to README.md

## Implementation Order

1. **PlayerService** ✅ - Core playback functionality with VLC integration
2. **PlayerView** ✅ - UI components for video display and OSD
3. **AppController Integration** ✅ - State machine and service binding
4. **MainWindow Integration** ✅ - View switching and layout management
5. **Database Support** ✅ - Resume position and video details tracking (already existed)
6. **Testing** ✅ - Comprehensive test coverage with mocking (634 tests, 98% coverage)
7. **Error Handling** ✅ - Robust error management and dependency checking
8. **Input Manager Updates** ✅ - Context-specific key routing via controller
9. **Documentation** - Complete documentation updates (pending, low priority)

## Key Technical Challenges

- **VLC Integration**: Proper embedding of VLC video output in PyQt QFrame using winId()
- **Hardware Acceleration**: Ensuring VLC uses Pi 5 GPU acceleration
- **Audio Track Management**: External audio track loading and cycling
- **Resource Management**: Proper cleanup of VLC instances and resources
- **Testing**: Comprehensive mocking strategy for VLC dependencies

## Success Criteria

- [x] Video playback with VLC integration implemented (Pi 5 hardware acceleration configured)
- [x] Player controls respond correctly to all specified keyboard inputs
- [x] Navigation preserves context when exiting player (returns to exact previous state)
- [x] Resume position functionality works correctly (save on exit, restore on play)
- [x] Audio track cycling works for both original and voiceover tracks
- [x] All components have comprehensive test coverage (634 tests, 98% coverage)
- [x] Application handles all error conditions gracefully (via toast notifications)
- [x] VLC dependency checking fails fast if VLC missing (check_dependencies() in main.py)
- [x] All code follows development standards (type hints, docstrings, error handling)

## Dependencies

- **System**: VLC (must be installed on target system)
- **Python**: python-vlc (already in pyproject.toml)
- **Hardware**: Raspberry Pi 5 with hardware acceleration support
- **Database**: Existing SQLite database with video_files table
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4

## Data Integration Points

- **Video File Paths**: Resolved from `video_files.file_path` in database
- **Resume Positions**: Stored in `video_files.resume_position_seconds`
- **Voiceover Files**: Loaded from `voiceovers.file_path` when available
- **Audio Tracks**: Enumerated from VLC media player for track cycling

## Standards Compliance

- **Type Hints**: Mandatory on all function signatures
- **Docstrings**: Required on all classes and public methods
- **Error Handling**: Specific exceptions only (`vlc.VLCException`)
- **Testing**: MockPlayerService, pytest-qt, in-memory SQLite
- **Logging**: Standard format `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- **No Logic in Views**: PlayerView communicates via signals only