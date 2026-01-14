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

### 2. PlayerView Implementation

**File**: `src/ui/components/player_view.py` (CREATE)

**Specification**: Reference `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 3.3

**Tasks**:
- [ ] Create PlayerView class inheriting from QWidget with complete type hints
- [ ] Implement full-screen layout with black background
- [ ] Add QFrame widget for VLC video output using winId() integration
  - **Source**: `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 3.3
- [ ] Implement On-Screen Display (OSD) with minimal icons only
  - **Source**: `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 4.3
- [ ] Add OSD components: pause icon, seek icons, volume icon, audio track indicator
- [ ] Implement OSD fade-out after 3 seconds of inactivity using QTimer
- [ ] Add mouse cursor hiding for full-screen experience
- [ ] Implement keyboard input handling integration with InputManager
- [ ] Add methods for showing/hiding specific OSD elements with type hints
- [ ] Create audio track selection overlay for L key functionality
- [ ] Add proper styling consistent with application theme
- [ ] Create unit tests with widget mocking using pytest-qt
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.3

**Dependencies**:
- PyQt5.QtWidgets for QWidget and layout
- PyQt5.QtCore for QTimer (OSD fade)
- Integration with existing UI styles

### 3. AppController Player Integration

**File**: `src/controllers/app_controller.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/03_COMPONENT_INTERFACES.md` section 1.1

**Tasks**:
- [ ] Complete PlayerActiveHandler implementation (lines 205-220) with type hints
- [ ] Add handling for TOGGLE_PAUSE, SEEK_FORWARD, SEEK_BACKWARD actions
  - **Source**: `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 3.5
- [ ] Add handling for VOLUME_UP, VOLUME_DOWN, TOGGLE_MUTE actions
- [ ] Add handling for CYCLE_AUDIO action with track switching
- [ ] Implement `play_media(self, file_id: int) -> None` method to prepare PlayerService
- [ ] Add service binding methods for PlayerService with type hints
- [ ] Implement player activation logic in `activate_selected()` method (line 577)
  - **Current**: Shows "Player not implemented yet" toast
- [ ] Add proper state transition to PLAYER_ACTIVE when playing media
- [ ] Implement resume position saving on player exit (ESC key)
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4 (resume_position_seconds)
- [ ] Add signal connections for PlayerService events with type hints
- [ ] Implement navigation context preservation for player exit
- [ ] Add error handling for player initialization failures

**Integration Points**:
- Modify `bind_services()` method to accept PlayerService
- Add signal handlers: `_on_playback_finished()`, `_on_time_changed()`, `_on_player_error()`

### 4. MainWindow Player Integration

**File**: `src/ui/windows/main_window.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 4.3

**Tasks**:
- [ ] Add PlayerView instance to MainWindow layout
- [ ] Implement view switching between LibraryView and PlayerView
- [ ] Add `show_player(self) -> None` and `hide_player(self) -> None` methods
- [ ] Integrate PlayerView with InputManager event routing
- [ ] Add proper focus management for player state
- [ ] Implement status bar updates for player state (time, progress)
- [ ] Add toast notification integration for player errors

### 5. Database Player Support

**File**: `src/database/db_manager.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4

**Tasks**:
- [ ] Add `update_resume_position(self, file_id: int, position_seconds: int) -> None` method
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.4
- [ ] Implement `get_video_details(self, media_id: str) -> dict | None` method for player initialization
- [ ] Add voiceover file path tracking in video details queries
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 3.6
- [ ] Implement file path resolution for video files
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 1.2

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

### 7. Testing Implementation (PARTIAL)

**Files**: `tests/test_player_service.py` (CREATE), `tests/test_player_view.py` (CREATE)

**Specification**: Reference `assets/docs/architecture/06_DEV_STANDARDS.md` section 4

**Tasks**:
- [x] Create `tests/test_player_service.py` with VLC mocking (54 tests, 97% coverage)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.2
- [ ] Create `tests/test_player_view.py` with pytest-qt
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 4.3
- [ ] Add player state tests to `tests/test_app_controller.py` (MODIFY)
- [ ] Add integration tests for complete player workflow
- [ ] Ensure 100% test coverage for all new components
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 3.5

### 8. Error Handling and Recovery (PARTIAL)

**Tasks**:
- [ ] Implement VLC dependency checking in main.py (MODIFY)
  - **Source**: `assets/docs/architecture/06_DEV_STANDARDS.md` section 6
- [x] Add proper error handling for VLC initialization failures (in PlayerService)
- [x] Implement file existence validation before playback (in PlayerService.load_video)
  - **Source**: `assets/docs/architecture/02_DATA_DESIGN.md` section 5.2
- [ ] Add storage space validation for media files
- [x] Implement proper cleanup of VLC resources (PlayerService.release method)

### 9. Input Manager Updates

**File**: `src/ui/input_manager.py` (MODIFY)

**Specification**: Reference `assets/docs/architecture/04_UI_UX_STATE_MACHINE.md` section 3.5

**Tasks**:
- [ ] Verify player action mappings are complete (lines 167-173)
- [ ] Add context-specific key routing for PLAYER_ACTIVE state
- [ ] Ensure proper debouncing for player control keys

### 10. Documentation and Integration

**Tasks**:
- [ ] Update AGENTS.md with Phase 4 commands and testing requirements
- [ ] Add PlayerService documentation to code docstrings
- [ ] Update system architecture documentation with Phase 4 components
- [ ] Document player controls and keyboard shortcuts
- [ ] Add VLC dependency notes to README.md

## Implementation Order

1. **PlayerService** - Core playback functionality with VLC integration
2. **PlayerView** - UI components for video display and OSD
3. **AppController Integration** - State machine and service binding
4. **MainWindow Integration** - View switching and layout management
5. **Database Support** - Resume position and video details tracking
6. **Testing** - Comprehensive test coverage with mocking
7. **Error Handling** - Robust error management and dependency checking
8. **Documentation** - Complete documentation updates

## Key Technical Challenges

- **VLC Integration**: Proper embedding of VLC video output in PyQt QFrame using winId()
- **Hardware Acceleration**: Ensuring VLC uses Pi 5 GPU acceleration
- **Audio Track Management**: External audio track loading and cycling
- **Resource Management**: Proper cleanup of VLC instances and resources
- **Testing**: Comprehensive mocking strategy for VLC dependencies

## Success Criteria

- [ ] Video playback with VLC integration works on Pi 5 with hardware acceleration
- [ ] Player controls respond correctly to all specified keyboard inputs
- [ ] Navigation preserves context when exiting player (returns to exact previous state)
- [ ] Resume position functionality works correctly
- [ ] Audio track cycling works for both original and voiceover tracks
- [ ] All components have 100% test coverage with proper mocking
- [ ] Application handles all error conditions gracefully
- [ ] VLC dependency checking fails fast if VLC missing
- [ ] All code follows development standards (type hints, docstrings, error handling)

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