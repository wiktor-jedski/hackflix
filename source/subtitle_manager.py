# --- START OF FILE source/subtitle_manager.py ---

"""
Subtitle manager module for the Raspberry Pi Movie Player App.
Handles interactions with the OpenSubtitles.com REST API v1.
"""

import os
import traceback

import requests
import json
import time
import threading
from urllib.parse import urljoin, urlencode
from dotenv import load_dotenv

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# --- Configuration Placeholders ---
load_dotenv()
# Replace with your actual credentials and App details
OPENSUBTITLES_API_KEY = os.environ.get("OPENSUBTITLES_API_KEY")
OPENSUBTITLES_USERNAME = os.environ.get("OPENSUBTITLES_USERNAME") # Optional, for >5 downloads/day
OPENSUBTITLES_PASSWORD = os.environ.get("OPENSUBTITLES_PASSWORD") # Optional, for >5 downloads/day
APP_USER_AGENT = "HackFlix v0.1.0" # Replace with your app name and version
# --- End Configuration ---

API_BASE_URL = "https://api.opensubtitles.com/api/v1/"

class SubtitleManager(QObject):
    """
    Manages searching and downloading subtitles from OpenSubtitles.
    """

    # Signals
    login_status = pyqtSignal(bool, str) # success (bool), message/error (str)
    search_results = pyqtSignal(list) # List of subtitle results (dicts)
    search_error = pyqtSignal(str) # Error message
    download_ready = pyqtSignal(str, str) # download_link (str), suggested_filename(str)
    download_error = pyqtSignal(dict) # Error message
    quota_info = pyqtSignal(int, int) # remaining downloads, allowed downloads

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = OPENSUBTITLES_API_KEY
        self.username = OPENSUBTITLES_USERNAME
        self.password = OPENSUBTITLES_PASSWORD
        self.user_agent = APP_USER_AGENT

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Api-Key": self.api_key,
            "User-Agent": self.user_agent,
            "Content-Type": "application/json" # Default Content-Type
        })

        self.base_url = API_BASE_URL
        self.jwt_token = None
        self.user_info = None
        self.logged_in = False

    def _make_request(self, method, endpoint, params=None, data=None, requires_auth=False):
        """Helper function to make API requests."""
        url = urljoin(self.base_url, endpoint)
        headers = self.session.headers.copy()

        if requires_auth:
            if not self.jwt_token:
                return None, {"message": "Login required for this operation.", "status": 401}
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        try:
            response = self.session.request(
                method,
                url,
                params=params, # GET params
                json=data,     # POST/PUT/DELETE body (automatically sets Content-Type to application/json)
                headers=headers,
                timeout=20 # Increased timeout for potential network latency
            )

            # Update quota info from headers if available
            remaining = response.headers.get('ratelimit-remaining')
            limit = response.headers.get('ratelimit-limit')
            if remaining is not None and limit is not None:
                 try:
                     self.quota_info.emit(int(remaining), int(limit))
                 except ValueError:
                     pass # Ignore if headers are not integers

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2)) # Default wait 2s
                print(f"Rate limit hit. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                # Retry the request once
                response = self.session.request(method, url, params=params, json=data, headers=headers, timeout=20)

            # Attempt to parse JSON response, handle errors
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                # Handle cases where response is not JSON (e.g., unexpected errors)
                 if response.ok: # 2xx status but no JSON body? Unusual.
                      response_data = {"message": "Request successful but no JSON body received.", "status": response.status_code}
                 else:
                      response_data = {"message": response.text or f"HTTP Error {response.status_code}", "status": response.status_code}


            # Check for errors indicated by status code even if JSON parsing succeeded
            if not response.ok:
                 # Ensure there's a message field, use response text if missing
                 if 'message' not in response_data:
                      response_data['message'] = response.text or f"API Error {response.status_code}"
                 # Ensure status is set correctly
                 response_data.setdefault('status', response.status_code)
                 print(f"API Error {response.status_code} on {endpoint}: {response_data.get('message')}")
                 return None, response_data # Return error details


            return response_data, None # Return data, no error

        except requests.exceptions.RequestException as e:
            print(f"Network Error on {endpoint}: {e}")
            return None, {"message": f"Network Error: {e}", "status": 500}
        except Exception as e: # Catch unexpected errors
             print(f"Unexpected Error on {endpoint}: {e}\n{traceback.format_exc()}")
             return None, {"message": f"Unexpected Error: {e}", "status": 500}

    def login(self):
        """Login to OpenSubtitles to get JWT token for extended limits."""
        if not self.username or not self.password:
            self.login_status.emit(False, "Username or Password not configured.")
            return

        endpoint = "login"
        payload = {"username": self.username, "password": self.password}

        def _login_thread():
            data, error = self._make_request("POST", endpoint, data=payload)
            if error:
                self.logged_in = False
                self.jwt_token = None
                self.user_info = None
                self.login_status.emit(False, f"Login failed ({error.get('status', 'N/A')}): {error.get('message', 'Unknown error')}")
            elif data and data.get("token"):
                self.logged_in = True
                self.jwt_token = data["token"]
                self.user_info = data.get("user")
                # Optional: Switch base_url if provided (for VIP users etc.)
                # self.base_url = f"https://{data.get('base_url', 'api.opensubtitles.com')}/api/v1/"
                print(f"Login successful. User Level: {self.user_info.get('level', 'N/A')}, Allowed Downloads: {self.user_info.get('allowed_downloads', 'N/A')}")
                self.login_status.emit(True, "Login successful.")
                # Emit initial quota info after login
                if self.user_info:
                    self.quota_info.emit(self.user_info.get('allowed_downloads', 0), self.user_info.get('allowed_downloads', 0))
            else:
                 # Handle cases where login returns 200 OK but no token (shouldn't happen per docs)
                 self.logged_in = False
                 self.jwt_token = None
                 self.user_info = None
                 self.login_status.emit(False, "Login failed: Invalid response from server.")

        threading.Thread(target=_login_thread, daemon=True).start()

    def logout(self):
        """Logout from OpenSubtitles."""
        if not self.jwt_token:
            return # Not logged in

        endpoint = "logout"

        def _logout_thread():
            # Logout doesn't technically require auth header per docs, but doesn't hurt
            _, error = self._make_request("DELETE", endpoint, requires_auth=True)
            self.logged_in = False
            self.jwt_token = None
            self.user_info = None
            if error:
                print(f"Logout failed: {error.get('message', 'Unknown error')}")
            else:
                print("Logout successful.")

        threading.Thread(target=_logout_thread, daemon=True).start()

    def search_subtitles(self, query=None, imdb_id=None, languages=None, tmdb_id=None, moviehash=None, season=None, episode=None):
        """
        Search for subtitles. At least one identifier (query, imdb_id, etc.) is needed.

        Args:
            query (str, optional): Filename or movie title.
            imdb_id (str, optional): IMDB ID (e.g., 'tt0123456').
            languages (str, optional): Comma-separated language codes (e.g., 'en,pl').
            tmdb_id (int, optional): TMDB ID.
            moviehash (str, optional): 16-byte movie hash.
            season (int, optional): Season number for episodes.
            episode (int, optional): Episode number for episodes.
        """
        endpoint = "subtitles"
        params = {}

        if query: params['query'] = query
        if imdb_id:
             # Remove 'tt' and leading zeros as recommended
             params['imdb_id'] = imdb_id.lower().replace('tt', '').lstrip('0')
        if tmdb_id: params['tmdb_id'] = tmdb_id
        if moviehash: params['moviehash'] = moviehash
        if languages: params['languages'] = languages.lower() # Ensure lowercase
        if season is not None: params['season_number'] = season
        if episode is not None: params['episode_number'] = episode
        if season is not None or episode is not None:
             params['type'] = 'episode' # Assume episode type if season/episode provided
        else:
            params['type'] = 'movie' # Default to movie type

        if not params or not any([query, imdb_id, tmdb_id, moviehash]):
            self.search_error.emit("Search requires at least one identifier (query, imdb_id, tmdb_id, or moviehash).")
            return

        # Sort parameters alphabetically for potential caching/performance gains
        sorted_params = dict(sorted(params.items()))

        def _search_thread():
            data, error = self._make_request("GET", endpoint, params=sorted_params)
            if error:
                self.search_error.emit(f"Search failed ({error.get('status', 'N/A')}): {error.get('message', 'Unknown error')}")
            elif data and 'data' in data:
                # Process results: Extract relevant fields
                processed_results = []
                for item in data['data']:
                     attributes = item.get('attributes', {})
                     file_info = attributes.get('files', [{}])[0] # Get first file info
                     feature_details = attributes.get('feature_details', {})

                     processed = {
                         'id': item.get('id'), # subtitle ID
                         'type': item.get('type'), # subtitle type
                         'language': attributes.get('language'),
                         'download_count': attributes.get('download_count'),
                         'new_download_count': attributes.get('new_download_count'),
                         'hearing_impaired': attributes.get('hearing_impaired'),
                         'hd': attributes.get('hd'),
                         'fps': attributes.get('fps'),
                         'votes': attributes.get('votes'),
                         'points': attributes.get('points'),
                         'ratings': attributes.get('ratings'),
                         'from_trusted': attributes.get('from_trusted'),
                         'foreign_parts_only': attributes.get('foreign_parts_only'),
                         'ai_translated': attributes.get('ai_translated'),
                         'machine_translated': attributes.get('machine_translated'),
                         'upload_date': attributes.get('upload_date'),
                         'release': attributes.get('release'),
                         'comments': attributes.get('comments'),
                         'legacy_subtitle_id': attributes.get('legacy_subtitle_id'),
                         'uploader': attributes.get('uploader', {}).get('name', 'Unknown'),
                         'feature_title': feature_details.get('title', 'N/A'),
                         'feature_year': feature_details.get('year'),
                         'feature_imdb_id': feature_details.get('imdb_id'),
                         'feature_tmdb_id': feature_details.get('tmdb_id'),
                         'file_id': file_info.get('file_id'), # Crucial for download
                         'file_name': file_info.get('file_name', 'subtitle.srt') # Suggested filename
                     }
                     processed_results.append(processed)

                self.search_results.emit(processed_results)
            else:
                # Handle empty results or unexpected response structure
                if data and data.get('total_count', 0) == 0:
                     self.search_results.emit([]) # Emit empty list for no results
                else:
                     self.search_error.emit(f"Search failed: Invalid response format. {data}")

        threading.Thread(target=_search_thread, daemon=True).start()

    def request_download(self, file_id):
        """
        Request a download link for a specific subtitle file_id.
        Requires user login for more than 5 downloads/day.
        """
        if not file_id:
            self.download_error.emit("File ID is required for download.")
            return

        endpoint = "download"
        payload = {"file_id": int(file_id)} # API expects integer

        # Check if login is needed based on quota/policy (simplistic check: assume needed if username set)
        # A more robust check would involve tracking the remaining anonymous downloads
        login_potentially_required = bool(self.username and self.password)

        def _download_thread():
            data, error = self._make_request("POST", endpoint, data=payload, requires_auth=self.logged_in)

            if error:
                 self.download_error.emit(error)
            elif data and data.get("link"):
                # Emit remaining count along with the link
                remaining = data.get('remaining', -1)
                print(f"Download link obtained. Remaining downloads: {remaining}")
                if remaining != -1 and self.user_info: # Update user info quota if logged in
                      # Be careful directly modifying user_info if it's used elsewhere
                      pass # self.user_info['allowed_downloads'] = remaining? API doesn't guarantee this reflects total allowed

                # Emit the download link and the filename from the response
                self.download_ready.emit(data['link'], data.get('file_name', f'{file_id}.srt'))
            else:
                # Create a generic error dict for invalid success response
                fallback_error = {"message": f"Download failed: Invalid response from server.", "status": 500}
                self.download_error.emit(fallback_error)  # EMIT DICT

        threading.Thread(target=_download_thread, daemon=True).start()

    def download_subtitle_file(self, download_link, save_path):
        """
        Downloads the actual subtitle file from the provided link.

        Args:
            download_link (str): The temporary download URL from request_download.
            save_path (str): The full path where the SRT file should be saved.
        """
        try:
            # Use a separate requests call, no API key/auth needed for the link itself
            response = requests.get(download_link, timeout=30, stream=True)
            response.raise_for_status() # Check for errors (like 410 Gone for expired link)

            # Ensure the directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save the file (UTF-8 as promised by API)
            with open(save_path, 'wb') as f: # Open in binary write mode
                 for chunk in response.iter_content(chunk_size=8192):
                      f.write(chunk)

            print(f"Subtitle downloaded successfully to: {save_path}")
            return True, None # Success

        except requests.exceptions.Timeout:
             error_msg = f"Timeout downloading subtitle from link: {download_link}"
             print(error_msg)
             return False, error_msg
        except requests.exceptions.HTTPError as e:
             error_msg = f"HTTP Error {e.response.status_code} downloading subtitle from link ({download_link}): {e.response.text}"
             print(error_msg)
             return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error downloading subtitle from link ({download_link}): {e}"
            print(error_msg)
            return False, error_msg
        except IOError as e:
            error_msg = f"Failed to write subtitle file to {save_path}: {e}"
            print(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error downloading subtitle file: {e}\n{traceback.format_exc()}"
            print(error_msg)
            return False, error_msg

# Example Usage (for testing)
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLineEdit, QLabel
    from PyQt5.QtCore import QTimer

    # Dummy App to test signals
    class TestApp(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Subtitle Manager Test")
            self.layout = QVBoxLayout()

            self.manager = SubtitleManager()

            # --- UI Elements ---
            self.login_button = QPushButton("Login (if configured)")
            self.search_query_input = QLineEdit()
            self.search_query_input.setPlaceholderText("Search Query (e.g., movie title)")
            self.search_imdb_input = QLineEdit()
            self.search_imdb_input.setPlaceholderText("IMDb ID (e.g., tt0133093)")
            self.search_lang_input = QLineEdit("en")
            self.search_lang_input.setPlaceholderText("Languages (e.g., en,pl)")
            self.search_button = QPushButton("Search Subtitles")
            self.results_display = QTextEdit()
            self.results_display.setReadOnly(True)
            self.download_id_input = QLineEdit()
            self.download_id_input.setPlaceholderText("File ID from results")
            self.download_button = QPushButton("Request Download Link")
            self.status_label = QLabel("Status: Idle")

            # --- Layout ---
            self.layout.addWidget(self.login_button)
            self.layout.addWidget(QLabel("--- Search ---"))
            self.layout.addWidget(self.search_query_input)
            self.layout.addWidget(self.search_imdb_input)
            self.layout.addWidget(self.search_lang_input)
            self.layout.addWidget(self.search_button)
            self.layout.addWidget(QLabel("--- Results ---"))
            self.layout.addWidget(self.results_display)
            self.layout.addWidget(QLabel("--- Download ---"))
            self.layout.addWidget(self.download_id_input)
            self.layout.addWidget(self.download_button)
            self.layout.addWidget(self.status_label)
            self.setLayout(self.layout)

            # --- Connections ---
            self.login_button.clicked.connect(self.manager.login)
            self.search_button.clicked.connect(self.do_search)
            self.download_button.clicked.connect(self.do_download_request)

            self.manager.login_status.connect(self.on_login_status)
            self.manager.search_results.connect(self.on_search_results)
            self.manager.search_error.connect(self.on_search_error)
            self.manager.download_ready.connect(self.on_download_ready)
            self.manager.download_error.connect(self.on_download_error)
            self.manager.quota_info.connect(self.on_quota_info)

            self.resize(600, 700)

            # Auto-login if configured
            if self.manager.username and self.manager.password:
                 QTimer.singleShot(500, self.manager.login) # Delay slightly

        def on_login_status(self, success, message):
            self.status_label.setText(f"Login Status: {message}")

        def on_quota_info(self, remaining, limit):
            self.status_label.setText(f"Quota: {remaining}/{limit} downloads remaining.")

        def do_search(self):
            query = self.search_query_input.text().strip()
            imdb_id = self.search_imdb_input.text().strip()
            langs = self.search_lang_input.text().strip()
            self.results_display.clear()
            self.status_label.setText("Searching...")
            self.manager.search_subtitles(query=query or None, imdb_id=imdb_id or None, languages=langs or "en") # Default to English if empty

        def on_search_results(self, results):
            self.status_label.setText(f"Search complete. Found {len(results)} subtitles.")
            if not results:
                self.results_display.setText("No results found.")
                return

            display_text = ""
            for res in results:
                display_text += f"--- Result ---\n"
                display_text += f"  Lang: {res.get('language', 'N/A')}, Rel: {res.get('release', 'N/A')}\n"
                display_text += f"  File: {res.get('file_name', 'N/A')}\n"
                display_text += f"  Feat: {res.get('feature_title', 'N/A')} ({res.get('feature_year', 'N/A')})\n"
                display_text += f"  Votes: {res.get('votes', 0)}, Rating: {res.get('ratings', 0):.1f}, HD: {res.get('hd', False)}\n"
                display_text += f"  File ID: {res.get('file_id', 'N/A')} (Use this to download)\n"
                display_text += f"  Uploader: {res.get('uploader', 'N/A')}\n\n"
            self.results_display.setText(display_text)

        def on_search_error(self, message):
            self.status_label.setText(f"Search Error: {message}")
            self.results_display.setText(f"Error:\n{message}")

        def do_download_request(self):
            file_id = self.download_id_input.text().strip()
            if not file_id.isdigit():
                self.status_label.setText("Download Error: Invalid File ID.")
                return
            self.status_label.setText(f"Requesting download for File ID: {file_id}...")
            self.manager.request_download(int(file_id))

        def on_download_ready(self, link, filename):
            self.status_label.setText(f"Download Ready! Link obtained.")
            self.results_display.append(f"\n--- Download Ready ---\nLink: {link}\nSuggested Filename: {filename}\n")
            # In real app, trigger the actual download here
            save_dir = os.path.expanduser("~/Downloads/HackFlix_Subs") # Example save dir
            save_path = os.path.join(save_dir, filename)
            self.status_label.setText(f"Downloading to {save_path}...")
            # Run download in a separate thread to avoid blocking GUI
            threading.Thread(target=self._download_file_thread, args=(link, save_path), daemon=True).start()


        def _download_file_thread(self, link, save_path):
            success, error = self.manager.download_subtitle_file(link, save_path)
            # Need to signal back to the main thread to update UI safely
            # For simplicity here, just print
            if success:
                print(f"Background download finished successfully: {save_path}")
                # In a real app, you'd use another signal or QMetaObject.invokeMethod
                # self.status_label.setText(f"Download Successful: {save_path}")
            else:
                print(f"Background download failed: {error}")
                # self.status_label.setText(f"Download Failed: {error}")

        @pyqtSlot(dict)
        def on_download_error(self, error_details):
            status = error_details.get('status', 'N/A')
            message = error_details.get('message', 'Unknown Error')
            error_text = f"Status: {status}\nMessage: {message}"
            self.status_label.setText(f"Download Error: {status}")
            self.results_display.append(f"\n--- Download Error ---\n{error_text}\n")

        def closeEvent(self, event):
             # Attempt logout if logged in
             if self.manager.logged_in:
                  self.manager.logout()
                  time.sleep(0.5) # Give logout a moment
             event.accept()


    app = QApplication(sys.argv)
    # IMPORTANT: Check if placeholders are still default
    if OPENSUBTITLES_API_KEY == "YOUR_API_KEY_HERE":
         print("\n" + "*"*60)
         print(" WARNING: OpenSubtitles API Key placeholder not replaced!")
         print("          Subtitle functionality will likely fail.")
         print("          Edit source/subtitle_manager.py")
         print("*"*60 + "\n")
    elif OPENSUBTITLES_USERNAME != "YOUR_USERNAME_HERE" and OPENSUBTITLES_PASSWORD == "YOUR_PASSWORD_HERE":
         print("\n" + "*"*60)
         print(" WARNING: OpenSubtitles username is set, but password is not!")
         print("          Login for extended download limits will fail.")
         print("          Edit source/subtitle_manager.py")
         print("*"*60 + "\n")


    win = TestApp()
    win.show()
    sys.exit(app.exec_())
