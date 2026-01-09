"""Hackflix - Movie player application for Raspberry Pi 5.

Entry point for the application.
"""

import logging
import os
import sys

from src.config import (
    DATABASE_PATH,
    check_required_env_vars,
    ensure_directories,
    setup_logging,
)
from src.database import DatabaseManager

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
    setup_logging(debug=debug_mode)
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
            "Please install VLC and libtorrent."
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

    # Full application loop will be implemented in Phase 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
