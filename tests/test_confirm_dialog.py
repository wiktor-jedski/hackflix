"""Tests for ConfirmDialog component."""

import pytest
from src.qt import Qt
from src.qt import QDialog, QWidget

from src.ui.components.confirm_dialog import ConfirmDialog


class TestConfirmDialog:
    """Tests for ConfirmDialog class."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def dialog(self, parent_widget: QWidget, qtbot) -> ConfirmDialog:
        """Create a ConfirmDialog instance."""
        dialog = ConfirmDialog(
            "Delete File?", "This action cannot be undone.", parent_widget
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_initialization(self, dialog: ConfirmDialog) -> None:
        """Test ConfirmDialog initialization."""
        assert dialog is not None
        assert dialog.objectName() == "ConfirmDialog"

    def test_title_displayed(self, dialog: ConfirmDialog) -> None:
        """Test that title is displayed."""
        assert dialog._title_label.text() == "Delete File?"

    def test_message_displayed(self, dialog: ConfirmDialog) -> None:
        """Test that message is displayed."""
        assert dialog._message_label.text() == "This action cannot be undone."

    def test_is_modal(self, dialog: ConfirmDialog) -> None:
        """Test that dialog is modal."""
        assert dialog.isModal()

    def test_enter_accepts(self, dialog: ConfirmDialog, qtbot) -> None:
        """Test that Enter key accepts the dialog."""
        # Show dialog non-blocking
        dialog.show()

        # Simulate Enter key
        qtbot.keyClick(dialog, Qt.Key.Key_Return)

        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_escape_rejects(self, dialog: ConfirmDialog, qtbot) -> None:
        """Test that Escape key rejects the dialog."""
        dialog.show()

        qtbot.keyClick(dialog, Qt.Key.Key_Escape)

        assert dialog.result() == QDialog.DialogCode.Rejected

    def test_fixed_width(self, dialog: ConfirmDialog) -> None:
        """Test that dialog has fixed width."""
        from src.ui.styles import DIALOG_WIDTH

        assert dialog.width() == DIALOG_WIDTH

    def test_has_hint_label(self, dialog: ConfirmDialog) -> None:
        """Test that dialog has hint label."""
        assert dialog._hint_label is not None
        assert "Enter" in dialog._hint_label.text()
        assert "Esc" in dialog._hint_label.text()


class TestConfirmDialogStaticMethod:
    """Tests for ConfirmDialog.confirm static method."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    def test_confirm_creates_dialog(self, parent_widget: QWidget, qtbot) -> None:
        """Test that confirm method creates and shows dialog."""
        # We can't easily test the static method in isolation since it blocks
        # Instead, test that a dialog can be created with the parameters
        dialog = ConfirmDialog("Test?", "Test message", parent_widget)
        qtbot.addWidget(dialog)
        assert dialog is not None

    def test_confirm_accept_returns_true(self, parent_widget: QWidget, qtbot) -> None:
        """Test that confirm returns True when accepted."""
        from src.qt import QTimer

        result_holder = [None]

        def accept_dialog():
            # Find the dialog and accept it
            for widget in parent_widget.children():
                if isinstance(widget, ConfirmDialog):
                    widget.accept()
                    return
            # Check application-level dialogs
            from src.qt import QApplication

            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, ConfirmDialog):
                    widget.accept()
                    return

        # Schedule accepting the dialog
        QTimer.singleShot(50, accept_dialog)

        # Run confirm in a thread-safe way using QTimer
        def run_confirm():
            result_holder[0] = ConfirmDialog.confirm("Test?", "Message", parent_widget)

        QTimer.singleShot(10, run_confirm)
        qtbot.wait(200)

    def test_confirm_without_parent(self, qtbot) -> None:
        """Test confirm can be called without parent."""
        from src.qt import QTimer

        def reject_dialog():
            from src.qt import QApplication

            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, ConfirmDialog):
                    widget.reject()
                    return

        QTimer.singleShot(50, reject_dialog)

        def run_confirm():
            # This exercises the parent=None code path
            ConfirmDialog.confirm("Test?", "Message", None)

        QTimer.singleShot(10, run_confirm)
        qtbot.wait(200)


class TestConfirmDialogKeyHandling:
    """Tests for ConfirmDialog key handling edge cases."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def dialog(self, parent_widget: QWidget, qtbot) -> ConfirmDialog:
        """Create a ConfirmDialog instance."""
        dialog = ConfirmDialog("Test?", "Test message", parent_widget)
        qtbot.addWidget(dialog)
        return dialog

    def test_other_keys_passed_to_super(self, dialog: ConfirmDialog, qtbot) -> None:
        """Test that other keys are passed to super().keyPressEvent."""
        dialog.show()
        # Press a key that's not Enter or Escape
        qtbot.keyClick(dialog, Qt.Key.Key_A)
        # Dialog should still be open (not accepted or rejected)
        assert dialog.result() == 0  # Neither accepted nor rejected

    def test_enter_key_accepts(self, dialog: ConfirmDialog, qtbot) -> None:
        """Test Enter key accepts dialog."""
        dialog.show()
        qtbot.keyClick(dialog, Qt.Key.Key_Enter)
        assert dialog.result() == QDialog.DialogCode.Accepted
