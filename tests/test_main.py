"""Test main.py entry point."""

import os
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.config import LoggingConfig
from src.main import check_dependencies, main


class TestCheckDependencies(unittest.TestCase):
    """Test dependency checking."""

    @patch.dict("sys.modules", {"vlc": None})
    def test_missing_vlc(self):
        """Test when VLC is missing."""
        with patch("src.main.logger") as mock_logger:
            result = check_dependencies()

            self.assertFalse(result)
            mock_logger.error.assert_called_once()
            # Get the actual message by checking the formatting arguments
            args, kwargs = mock_logger.error.call_args
            self.assertEqual(args[0], "Missing required dependencies: %s")
            self.assertIn("python-vlc (VLC)", args[1])

    @patch.dict("sys.modules", {"libtorrent": None})
    def test_missing_libtorrent(self):
        """Test when libtorrent is missing."""
        with patch("src.main.logger") as mock_logger:
            result = check_dependencies()

            self.assertFalse(result)
            mock_logger.error.assert_called_once()
            args, kwargs = mock_logger.error.call_args
            self.assertEqual(args[0], "Missing required dependencies: %s")
            self.assertIn("libtorrent", args[1])

    @patch.dict("sys.modules", {"vlc": None, "libtorrent": None})
    def test_missing_both_dependencies(self):
        """Test when both dependencies are missing."""
        with patch("src.main.logger") as mock_logger:
            result = check_dependencies()

            self.assertFalse(result)
            mock_logger.error.assert_called_once()
            args, kwargs = mock_logger.error.call_args
            self.assertEqual(args[0], "Missing required dependencies: %s")
            # Both should be in the formatted string
            self.assertIn("python-vlc (VLC)", args[1])
            self.assertIn("libtorrent", args[1])

    def test_all_dependencies_available(self):
        """Test when all dependencies are available."""
        with patch("src.main.logger") as mock_logger:
            result = check_dependencies()

            self.assertTrue(result)
            mock_logger.error.assert_not_called()


class TestMain(unittest.TestCase):
    """Test main entry point."""

    def setUp(self):
        """Set up test environment."""
        # Clean environment variables
        if "DEBUG" in os.environ:
            del os.environ["DEBUG"]

    @patch.dict(os.environ, {"DEBUG": "true"})
    @patch("src.main.QApplication")
    @patch("src.main.setup_translations")
    @patch("src.main.MainWindow")
    @patch("src.main.AppController")
    @patch("src.main.MetadataService")
    @patch("src.main.TorrentService")
    @patch("src.main.DatabaseManager")
    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_debug_mode(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
        mock_db_manager,
        mock_torrent_service,
        mock_metadata_service,
        mock_app_controller,
        mock_main_window,
        mock_setup_translations,
        mock_qapplication,
    ):
        """Test main with debug mode enabled."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = []
        mock_db_instance = MagicMock()
        mock_db_instance.get_incomplete_downloads.return_value = []
        mock_db_instance.get_incomplete_pipelines.return_value = []
        mock_db_manager.return_value = mock_db_instance

        mock_app_instance = MagicMock()
        mock_app_controller.return_value = mock_app_instance

        mock_qapp_instance = MagicMock()
        mock_qapp_instance.exec_.return_value = 0
        mock_qapplication.return_value = mock_qapp_instance

        result = main()

        self.assertEqual(result, 0)
        mock_setup_logging.assert_called_once_with(LoggingConfig(debug=True))
        mock_ensure_dirs.assert_called_once()

    @patch("src.main.QApplication")
    @patch("src.main.setup_translations")
    @patch("src.main.MainWindow")
    @patch("src.main.AppController")
    @patch("src.main.MetadataService")
    @patch("src.main.TorrentService")
    @patch("src.main.DatabaseManager")
    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_missing_env_vars(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
        mock_db_manager,
        mock_torrent_service,
        mock_metadata_service,
        mock_app_controller,
        mock_main_window,
        mock_setup_translations,
        mock_qapplication,
    ):
        """Test main with missing environment variables."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = ["GEMINI_API_KEY", "OPENSUBTITLES_API_KEY"]
        mock_db_instance = MagicMock()
        mock_db_instance.get_incomplete_downloads.return_value = []
        mock_db_instance.get_incomplete_pipelines.return_value = []
        mock_db_manager.return_value = mock_db_instance

        mock_app_instance = MagicMock()
        mock_app_controller.return_value = mock_app_instance

        mock_qapp_instance = MagicMock()
        mock_qapp_instance.exec_.return_value = 0
        mock_qapplication.return_value = mock_qapp_instance

        result = main()

        self.assertEqual(result, 0)
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("Missing environment variables", warning_msg)

    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_missing_dependencies(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
    ):
        """Test main when dependencies are missing."""
        # Configure mocks
        mock_check_deps.return_value = False
        mock_check_env.return_value = []

        result = main()

        self.assertEqual(result, 1)
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        self.assertIn("Required system dependencies are missing", error_msg)

    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    @patch("src.main.DatabaseManager")
    def test_main_database_failure(
        self,
        mock_db_manager,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
    ):
        """Test main when database initialization fails."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = []
        mock_db_manager.side_effect = Exception("Database error")

        result = main()

        self.assertEqual(result, 1)
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        self.assertIn("Failed to initialize database", error_msg)

    @patch("src.main.QApplication")
    @patch("src.main.setup_translations")
    @patch("src.main.MainWindow")
    @patch("src.main.AppController")
    @patch("src.main.MetadataService")
    @patch("src.main.TorrentService")
    @patch("src.main.DatabaseManager")
    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_incomplete_tasks(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
        mock_db_manager,
        mock_torrent_service,
        mock_metadata_service,
        mock_app_controller,
        mock_main_window,
        mock_setup_translations,
        mock_qapplication,
    ):
        """Test main with incomplete tasks to resume."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = []
        mock_db_instance = MagicMock()
        mock_db_instance.get_incomplete_downloads.return_value = ["movie1", "movie2"]
        mock_db_instance.get_incomplete_pipelines.return_value = ["pipeline1"]
        mock_db_manager.return_value = mock_db_instance

        mock_app_instance = MagicMock()
        mock_app_controller.return_value = mock_app_instance

        mock_qapp_instance = MagicMock()
        mock_qapp_instance.exec_.return_value = 0
        mock_qapplication.return_value = mock_qapp_instance

        result = main()

        self.assertEqual(result, 0)
        # Check that incomplete tasks are logged by examining specific calls
        # Find specific calls we care about
        calls = [call[0] for call in mock_logger.info.call_args_list]
        downloads_call = next(
            call for call in calls if "%d incomplete downloads" in call[0]
        )
        pipelines_call = next(
            call for call in calls if "%d incomplete pipeline tasks" in call[0]
        )

        self.assertEqual(downloads_call[1], 2)
        self.assertEqual(pipelines_call[1], 1)

    @patch("src.main.QApplication")
    @patch("src.main.setup_translations")
    @patch("src.main.MainWindow")
    @patch("src.main.AppController")
    @patch("src.main.MetadataService")
    @patch("src.main.TorrentService")
    @patch("src.main.DatabaseManager")
    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_qapplication_exit_code(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
        mock_db_manager,
        mock_torrent_service,
        mock_metadata_service,
        mock_app_controller,
        mock_main_window,
        mock_setup_translations,
        mock_qapplication,
    ):
        """Test main returns QApplication exit code."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = []
        mock_db_instance = MagicMock()
        mock_db_instance.get_incomplete_downloads.return_value = []
        mock_db_instance.get_incomplete_pipelines.return_value = []
        mock_db_manager.return_value = mock_db_instance

        mock_app_instance = MagicMock()
        mock_app_controller.return_value = mock_app_instance

        mock_qapp_instance = MagicMock()
        mock_qapp_instance.exec_.return_value = 42  # Custom exit code
        mock_qapplication.return_value = mock_qapp_instance

        result = main()

        self.assertEqual(result, 42)

    @patch("src.main.QApplication")
    @patch("src.main.setup_translations")
    @patch("src.main.MainWindow")
    @patch("src.main.AppController")
    @patch("src.main.MetadataService")
    @patch("src.main.TorrentService")
    @patch("src.main.DatabaseManager")
    @patch("src.main.check_dependencies")
    @patch("src.main.check_required_env_vars")
    @patch("src.main.ensure_directories")
    @patch("src.main.setup_logging")
    @patch("src.main.logger")
    def test_main_application_setup(
        self,
        mock_logger,
        mock_setup_logging,
        mock_ensure_dirs,
        mock_check_env,
        mock_check_deps,
        mock_db_manager,
        mock_torrent_service,
        mock_metadata_service,
        mock_app_controller,
        mock_main_window,
        mock_setup_translations,
        mock_qapplication,
    ):
        """Test main application setup flow."""
        # Configure mocks
        mock_check_deps.return_value = True
        mock_check_env.return_value = []
        mock_db_instance = MagicMock()
        mock_db_instance.get_incomplete_downloads.return_value = []
        mock_db_instance.get_incomplete_pipelines.return_value = []
        mock_db_manager.return_value = mock_db_instance

        mock_app_instance = MagicMock()
        mock_app_controller.return_value = mock_app_instance

        mock_main_window_instance = MagicMock()
        mock_main_window.return_value = mock_main_window_instance

        mock_qapp_instance = MagicMock()
        mock_qapp_instance.exec_.return_value = 0
        mock_qapplication.return_value = mock_qapp_instance

        result = main()

        self.assertEqual(result, 0)

        # Check QApplication setup
        mock_qapplication.assert_called_once_with(sys.argv)
        mock_qapp_instance.setApplicationName.assert_called_once_with("Hackflix")

        # Check translations setup
        mock_setup_translations.assert_called_once()

        # Check main window setup
        mock_main_window.assert_called_once()
        mock_main_window_instance.show.assert_called_once()

        # Check controller setup
        mock_app_instance.bind_main_window.assert_called_once_with(
            mock_main_window_instance
        )
        mock_app_instance.bind_services.assert_called_once()
        mock_app_instance.bootstrap.assert_called_once()

        # Check logger startup message
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        logged_messages = " ".join(info_calls)
        self.assertIn("Hackflix starting up", logged_messages)
        self.assertIn("Hackflix initialization complete", logged_messages)
        self.assertIn("Starting application event loop", logged_messages)


if __name__ == "__main__":
    unittest.main()
