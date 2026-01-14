"""Hackflix - Movie player application for Raspberry Pi 5.

Entry point for the application.
"""

import logging
import os
import subprocess
import sys

from PyQt5.QtWidgets import QApplication

from src.config import (
    CACHE_DIR,
    CATALOG_URL,
    DATABASE_PATH,
    LoggingConfig,
    check_required_env_vars,
    ensure_directories,
    setup_logging,
)
from src.controllers.app_controller import AppController
from src.database import DatabaseManager
from src.services.metadata_service import MetadataService
from src.services.pipeline_service import PipelineService
from src.services.torrent_service import TorrentService
from src.ui.windows.main_window import MainWindow
from src.utils.i18n import setup_translations

logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """Check if required system dependencies are available.

    Returns:
        True if all dependencies are available, False otherwise.
    """
    missing = []

    # Check for VLC
    try:
        import vlc  # noqa: F401
    except ImportError:
        missing.append("python-vlc (VLC)")

    # Check for libtorrent
    try:
        import libtorrent  # noqa: F401
    except ImportError:
        missing.append("libtorrent")

    # Check for FFmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        missing.append("ffmpeg")

    if missing:
        logger.error("Missing required dependencies: %s", ", ".join(missing))
        return False

    return True


def main() -> int:
    """Application entry point.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Setup logging first
    debug_mode = os.environ.get("DEBUG", "false").lower() == "true"
    log_config = LoggingConfig(debug=debug_mode)
    setup_logging(log_config)
    logger.info("Hackflix starting up...")

    # Ensure required directories exist
    ensure_directories()

    # Check environment variables
    missing_vars = check_required_env_vars()
    if missing_vars:
        logger.warning(
            "Missing environment variables: %s. Some features may not work correctly.",
            ", ".join(missing_vars),
        )

    # Check system dependencies
    if not check_dependencies():
        logger.error(
            "Required system dependencies are missing. "
            "Please install VLC, libtorrent, and FFmpeg."
        )
        return 1

    # Initialize database
    try:
        db_manager = DatabaseManager(DATABASE_PATH)
        db_manager.initialize()
        logger.info("Database ready at %s", DATABASE_PATH)
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        return 1

    # Check for incomplete tasks to resume
    incomplete_downloads = db_manager.get_incomplete_downloads()
    if incomplete_downloads:
        logger.info(
            "Found %d incomplete downloads to resume", len(incomplete_downloads)
        )

    incomplete_pipelines = db_manager.get_incomplete_pipelines()
    if incomplete_pipelines:
        logger.info(
            "Found %d incomplete pipeline tasks to resume", len(incomplete_pipelines)
        )

    logger.info("Hackflix initialization complete")

    # Create Qt application
    # Force X11 backend for PyQt5 compatibility with Wayland
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv)
    app.setApplicationName("Hackflix")

    # Setup translations (Polish by default)
    setup_translations(app, "pl")

    # Create main window
    main_window = MainWindow()

    # Create controller
    controller = AppController(db_manager)
    controller.bind_main_window(main_window)

    # Create and bind services
    metadata_service = MetadataService(
        db_manager=db_manager,
        catalog_url=CATALOG_URL,
        cache_dir=CACHE_DIR,
    )
    torrent_service = TorrentService(db_manager=db_manager)
    pipeline_service = PipelineService(db_manager=db_manager)

    controller.bind_services(
        metadata_service=metadata_service,
        torrent_service=torrent_service,
        pipeline_service=pipeline_service,
    )

    # Bootstrap the controller
    controller.bootstrap()

    # Show the main window
    main_window.show()

    # Run the application event loop
    logger.info("Starting application event loop")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
