"""
3-phase progress display widget for download pipeline

Shows overall progress and detailed breakdown:
- Video download: 0-33%
- Subtitle download: 34-66%
- Translation: 67-100%
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import pyqtSlot


class ThreePhaseProgressBar(QWidget):
    """
    Display 3-phase download progress with detailed sub-progress

    Phases:
    1. Video: 0-33% of total
    2. Subtitles: 34-66% of total
    3. Translation: 67-100% of total
    """

    def __init__(self, parent=None):
        """Initialize progress widget"""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Overall progress
        self.overall_label = QLabel(self.tr("Overall Progress:"))
        self.overall_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.overall_label)

        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        layout.addWidget(self.overall_bar)

        # Phase details header
        details_label = QLabel(self.tr("Phase Details:"))
        details_label.setStyleSheet("margin-top: 10px; font-weight: bold;")
        layout.addWidget(details_label)

        # Video phase (0-33%)
        self.video_label = QLabel(self.tr("Video: 0%"))
        layout.addWidget(self.video_label)

        self.video_bar = QProgressBar()
        self.video_bar.setRange(0, 100)
        self.video_bar.setValue(0)
        layout.addWidget(self.video_bar)

        # Subtitle phase (34-66%)
        self.subtitle_label = QLabel(self.tr("Subtitles: 0%"))
        layout.addWidget(self.subtitle_label)

        self.subtitle_bar = QProgressBar()
        self.subtitle_bar.setRange(0, 100)
        self.subtitle_bar.setValue(0)
        layout.addWidget(self.subtitle_bar)

        # Translation phase (67-100%)
        self.translation_label = QLabel(self.tr("Translation: 0%"))
        layout.addWidget(self.translation_label)

        self.translation_bar = QProgressBar()
        self.translation_bar.setRange(0, 100)
        self.translation_bar.setValue(0)
        layout.addWidget(self.translation_bar)

        layout.addStretch()

    @pyqtSlot(str, float, float)
    def update_progress(self, phase: str, phase_progress: float, overall_progress: float):
        """
        Update progress bars based on current phase

        Args:
            phase: Current phase ('video', 'subtitles', 'translation')
            phase_progress: 0.0-100.0 progress within current phase
            overall_progress: 0.0-100.0 overall progress (0-33-66-100)
        """
        # Update overall bar
        self.overall_bar.setValue(int(overall_progress))
        self.overall_label.setText(
            self.tr(f"Overall Progress: {overall_progress:.0f}%")
        )

        if phase == 'video':
            # Video phase active
            self.video_bar.setValue(int(phase_progress))
            self.video_label.setText(
                self.tr(f"Video: {phase_progress:.0f}% ({overall_progress:.0f}% of total)")
            )
            # Reset other phases
            self.subtitle_bar.setValue(0)
            self.subtitle_label.setText(self.tr("Subtitles: 0%"))
            self.translation_bar.setValue(0)
            self.translation_label.setText(self.tr("Translation: 0%"))

        elif phase == 'subtitles':
            # Video complete, subtitle phase active
            self.video_bar.setValue(100)
            self.video_label.setText(self.tr("Video: 100% (Complete)"))

            self.subtitle_bar.setValue(int(phase_progress))
            self.subtitle_label.setText(
                self.tr(f"Subtitles: {phase_progress:.0f}% ({overall_progress:.0f}% of total)")
            )

            # Reset translation
            self.translation_bar.setValue(0)
            self.translation_label.setText(self.tr("Translation: 0%"))

        elif phase == 'translation':
            # Video and subtitle complete, translation phase active
            self.video_bar.setValue(100)
            self.video_label.setText(self.tr("Video: 100% (Complete)"))

            self.subtitle_bar.setValue(100)
            self.subtitle_label.setText(self.tr("Subtitles: 100% (Complete)"))

            self.translation_bar.setValue(int(phase_progress))
            self.translation_label.setText(
                self.tr(f"Translation: {phase_progress:.0f}% ({overall_progress:.0f}% of total)")
            )

    def reset(self):
        """Reset all progress bars to zero"""
        self.overall_bar.setValue(0)
        self.overall_label.setText(self.tr("Overall Progress: 0%"))

        self.video_bar.setValue(0)
        self.video_label.setText(self.tr("Video: 0%"))

        self.subtitle_bar.setValue(0)
        self.subtitle_label.setText(self.tr("Subtitles: 0%"))

        self.translation_bar.setValue(0)
        self.translation_label.setText(self.tr("Translation: 0%"))


def main():
    """Test the progress widget with animated progress"""
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
    from PyQt5.QtCore import QTimer

    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Three Phase Progress Bar Test")
    window.resize(500, 400)

    # Create central widget
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)

    # Add progress widget
    progress = ThreePhaseProgressBar()
    layout.addWidget(progress)

    # Add control buttons
    buttons_layout = QVBoxLayout()

    # Test button for video phase
    def test_video():
        progress.update_progress('video', 50.0, 16.5)

    video_btn = QPushButton("Test Video Phase (50%)")
    video_btn.clicked.connect(test_video)
    buttons_layout.addWidget(video_btn)

    # Test button for subtitle phase
    def test_subtitle():
        progress.update_progress('subtitles', 60.0, 53.0)

    subtitle_btn = QPushButton("Test Subtitle Phase (60%)")
    subtitle_btn.clicked.connect(test_subtitle)
    buttons_layout.addWidget(subtitle_btn)

    # Test button for translation phase
    def test_translation():
        progress.update_progress('translation', 80.0, 93.3)

    translation_btn = QPushButton("Test Translation Phase (80%)")
    translation_btn.clicked.connect(test_translation)
    buttons_layout.addWidget(translation_btn)

    # Reset button
    reset_btn = QPushButton("Reset")
    reset_btn.clicked.connect(progress.reset)
    buttons_layout.addWidget(reset_btn)

    # Animated test button
    test_timer = QTimer()
    test_progress = [0]

    def animate_progress():
        test_progress[0] += 1
        if test_progress[0] <= 33:
            # Video phase (0-33%)
            phase_progress = (test_progress[0] / 33.0) * 100
            progress.update_progress('video', phase_progress, test_progress[0])
        elif test_progress[0] <= 66:
            # Subtitle phase (34-66%)
            phase_progress = ((test_progress[0] - 33) / 33.0) * 100
            progress.update_progress('subtitles', phase_progress, test_progress[0])
        elif test_progress[0] <= 100:
            # Translation phase (67-100%)
            phase_progress = ((test_progress[0] - 66) / 34.0) * 100
            progress.update_progress('translation', phase_progress, test_progress[0])
        else:
            test_timer.stop()
            test_progress[0] = 0

    test_timer.timeout.connect(animate_progress)

    def start_animation():
        test_progress[0] = 0
        progress.reset()
        test_timer.start(50)  # Update every 50ms

    animate_btn = QPushButton("Animate Full Progress")
    animate_btn.clicked.connect(start_animation)
    buttons_layout.addWidget(animate_btn)

    layout.addLayout(buttons_layout)

    window.setCentralWidget(central_widget)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
