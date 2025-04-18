# --- START OF FILE source/web_browser_tab.py ---

"""
Web Browser Tab module for the Raspberry Pi Movie Player App.
Displays a web page (e.g., Filmweb) for movie discovery
and allows searching for the original title in the Downloads tab.
"""

import sys
from PyQt5.QtCore import QUrl, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QProgressBar, QApplication, QMessageBox
# Import QWebEngineView - requires PyQtWebEngine to be installed
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
except ImportError:
    print("ERROR: PyQtWebEngine is not installed. Please install it ('pip install PyQtWebEngine' or 'sudo apt install python3-pyqt5.qtwebengine')")
    # Fallback: Create dummy classes if import fails
    class QWebEngineView:
         def __init__(self, *args, **kwargs): print("QWebEngineView unavailable")
         def setUrl(self, *args, **kwargs): pass
         def url(self): return QUrl("")
         def back(self): pass
         def forward(self): pass
         def reload(self): pass
         def stop(self): pass
         def page(self): return None
         def title(self): return ""
         # Dummy signals
         loadStarted = pyqtSignal()
         loadProgress = pyqtSignal(int)
         loadFinished = pyqtSignal(bool)
         urlChanged = pyqtSignal(QUrl)
         titleChanged = pyqtSignal(str)

    class QWebEnginePage:
        def __init__(self, *args, **kwargs): pass
        def history(self): return None
        def runJavaScript(self, *args, **kwargs): pass # Callback won't be called

# --- Configuration ---
FILMWEB_URL = "https://www.filmweb.pl/"
# CSS Selector for the specific element containing the original title
ORIGINAL_TITLE_SELECTOR = "h2.filmCoverSection__originalTitle"
# --- End Configuration ---

class WebBrowserTab(QWidget):
    """
    A tab containing a QWebEngineView to display Filmweb and extract original titles.
    """
    # Signal to send the extracted original title to the main app
    search_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Navigation Bar ---
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(2, 2, 2, 2)

        self.back_button = QPushButton("< Back")
        self.forward_button = QPushButton("Forward >")
        self.reload_button = QPushButton("Reload")
        self.home_button = QPushButton("Home")
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL...")
        self.search_title_button = QPushButton("Search Original Title")
        self.search_title_button.setToolTip("Search for the displayed movie's original title in Downloads")

        nav_bar.addWidget(self.back_button)
        nav_bar.addWidget(self.forward_button)
        nav_bar.addWidget(self.reload_button)
        nav_bar.addWidget(self.home_button)
        nav_bar.addWidget(self.url_bar, 1) # URL bar takes most space
        nav_bar.addWidget(self.search_title_button) # Add the search button

        # --- Web View ---
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(FILMWEB_URL))

        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: none; background-color: transparent; }
            QProgressBar::chunk { background-color: #0078D7; /* Or use theme color */ }
        """)

        # --- Layout Assembly ---
        layout.addLayout(nav_bar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.browser, 1) # Browser view takes remaining space
        self.setLayout(layout)

        # --- Connect Signals ---
        # Check if browser object is valid (not the dummy class)
        if hasattr(self.browser, 'page') and self.browser.page():
             # Navigation Controls
             self.back_button.clicked.connect(self.browser.back)
             self.forward_button.clicked.connect(self.browser.forward)
             self.reload_button.clicked.connect(self.browser.reload)
             self.home_button.clicked.connect(self.go_home)
             self.url_bar.returnPressed.connect(self.navigate_to_url)

             # Connect the title search button
             self.search_title_button.clicked.connect(self.extract_and_search_title)

             # Browser State Updates
             self.browser.urlChanged.connect(self.update_url_bar)
             self.browser.urlChanged.connect(self.update_nav_buttons) # Update back/forward enable state
             self.browser.loadStarted.connect(lambda: self.progress_bar.setVisible(True))
             self.browser.loadProgress.connect(self.progress_bar.setValue)
             self.browser.loadFinished.connect(self.on_load_finished) # Use slot for button state
             # self.browser.titleChanged.connect(self.setWindowTitle) # Optional: Update main window title?

             # Initial button states
             self.update_nav_buttons()
             self.progress_bar.setVisible(False)
             self.search_title_button.setEnabled(False) # Disabled until a film page loads
        else:
             # Disable controls if web engine is not available
             print("WebBrowserTab: QWebEngineView unavailable. Disabling controls.")
             self.back_button.setEnabled(False)
             self.forward_button.setEnabled(False)
             self.reload_button.setEnabled(False)
             self.home_button.setEnabled(False)
             self.url_bar.setEnabled(False)
             self.search_title_button.setEnabled(False)

    def go_home(self):
        """Navigate back to the initial Filmweb URL."""
        self.browser.setUrl(QUrl(FILMWEB_URL))

    def navigate_to_url(self):
        """Navigate to the URL entered in the bar."""
        url_text = self.url_bar.text().strip()
        if not url_text: return
        if not url_text.startswith(('http://', 'https://')):
            url_text = 'https://' + url_text
        qurl = QUrl(url_text)
        if qurl.isValid():
            self.browser.setUrl(qurl)
        else:
            QMessageBox.warning(self, "Invalid URL", f"The entered URL is not valid:\n{url_text}")
            print(f"Invalid URL entered: {url_text}")

    @pyqtSlot(QUrl)
    def update_url_bar(self, qurl):
        """Update the URL bar with the current URL."""
        if not self.url_bar.hasFocus():
            self.url_bar.setText(qurl.toString())
            self.url_bar.setCursorPosition(0)

    @pyqtSlot()
    def update_nav_buttons(self):
        """Update the enabled state of back/forward buttons."""
        page = self.browser.page()
        can_go_back = False
        can_go_forward = False
        if page:
             history = page.history()
             if history:
                can_go_back = history.canGoBack()
                can_go_forward = history.canGoForward()

        self.back_button.setEnabled(can_go_back)
        self.forward_button.setEnabled(can_go_forward)

    @pyqtSlot(bool)
    def on_load_finished(self, ok):
        """Slot called when page load finishes. Updates progress bar and search button state."""
        self.progress_bar.setVisible(False)
        self.update_nav_buttons() # Update history state too

        # Enable search button only if load was successful and URL looks like a film page
        url_path = self.browser.url().path()
        # Heuristic: Filmweb film pages usually contain /film/
        is_film_page = ok and url_path is not None and "/film/" in url_path
        self.search_title_button.setEnabled(is_film_page)
        print(f"Load Finished: ok={ok}, URL={self.browser.url().toString()}, Search Button Enabled={is_film_page}") # Debug

    def extract_and_search_title(self):
        """Executes JS to get the original title and emits the search_requested signal."""
        page = self.browser.page()
        if page:
            print(f"Attempting to extract original title using selector: '{ORIGINAL_TITLE_SELECTOR}'")

            # --- JavaScript Code ---
            # Finds the element, clones it, removes the year div, returns trimmed text or null.
            js_code = f"""
            (function() {{
                var titleElement = document.querySelector('{ORIGINAL_TITLE_SELECTOR}');
                if (titleElement) {{
                    var clone = titleElement.cloneNode(true);
                    var yearElement = clone.querySelector('.filmCoverSection__year');
                    if (yearElement) {{
                        clone.removeChild(yearElement);
                    }}
                    return clone.textContent.trim();
                }} else {{
                    return null; // Indicate element not found
                }}
            }})();
            """
            # --- End JavaScript Code ---

            # Execute JS, result handled in the callback 'handle_javascript_result'
            page.runJavaScript(js_code, self.handle_javascript_result)
        else:
            QMessageBox.warning(self, "Error", "Web engine page not available to extract title.")
            print("Cannot run JavaScript: Browser page not available.")


    def handle_javascript_result(self, result):
        """ Callback function to process the result of the JavaScript execution """
        print(f"JavaScript result received: '{result}' (Type: {type(result)})") # Debug

        if result and isinstance(result, str):
            original_title = result.strip()
            if original_title:
                print(f"Extracted Original Title: '{original_title}'. Emitting signal.")
                self.search_requested.emit(original_title) # Emit the found title
            else:
                # JS returned a string, but it was empty after trimming
                print("JavaScript returned an empty string after trimming.")
                QMessageBox.information(self, "Title Not Found",
                                        "Could not automatically extract an original title from this page (result was empty). Please copy/paste manually.")
        else:
            # Element not found (JS returned null) or result wasn't a string
            print("Original title element not found or JS failed.")
            QMessageBox.information(self, "Title Not Found",
                                    f"Could not automatically find the original title element ('{ORIGINAL_TITLE_SELECTOR}') on this page. Please copy/paste manually.")

# --- END OF FILE source/web_browser_tab.py ---