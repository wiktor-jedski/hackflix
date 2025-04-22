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
OPENSUBTITLES_API_KEY = os.environ.get("OPENSUBTITLES_API_KEY")
OPENSUBTITLES_USERNAME = os.environ.get("OPENSUBTITLES_USERNAME") # Optional, for >5 downloads/day
OPENSUBTITLES_PASSWORD = os.environ.get("OPENSUBTITLES_PASSWORD") # Optional, for >5 downloads/day
APP_USER_AGENT = "HackFlix v0.1.0" # Replace with your app name and version
# --- End Configuration ---

API_BASE_URL = "https://api.opensubtitles.com/api/v1/"

# Translation helper (if needed outside QObject context)
def tr(text):
    return text

class SubtitleManager(QObject): # Inherit QObject to use self.tr()
    """
    Manages searching and downloading subtitles from OpenSubtitles.
    """

    # Signals
    login_status = pyqtSignal(bool, str)
    search_results = pyqtSignal(list)
    search_error = pyqtSignal(str)
    download_ready = pyqtSignal(str, str)
    download_error = pyqtSignal(dict)
    quota_info = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent) # Call QObject initializer
        self.api_key = OPENSUBTITLES_API_KEY
        self.username = OPENSUBTITLES_USERNAME
        self.password = OPENSUBTITLES_PASSWORD
        self.user_agent = APP_USER_AGENT

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Api-Key": self.api_key,
            "User-Agent": self.user_agent,
            "Content-Type": "application/json"
        })

        self.base_url = API_BASE_URL
        self.jwt_token = None
        self.user_info = None
        self.logged_in = False

    def _make_request(self, method, endpoint, params=None, data=None, requires_auth=False):
        url = urljoin(self.base_url, endpoint); headers = self.session.headers.copy()
        if requires_auth:
            if not self.jwt_token: return None, {"message": self.tr("Login required."), "status": 401}
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        try:
            response = self.session.request(method,url,params=params,json=data,headers=headers,timeout=20)
            remaining = response.headers.get('ratelimit-remaining'); limit = response.headers.get('ratelimit-limit')
            if remaining is not None and limit is not None:
                 try: self.quota_info.emit(int(remaining), int(limit))
                 except ValueError: pass
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2)); print(f"Rate limit. Retrying after {retry_after}s...")
                time.sleep(retry_after); response = self.session.request(method, url, params=params, json=data, headers=headers, timeout=20)
            try: response_data = response.json()
            except json.JSONDecodeError: response_data = {"message": response.text or self.tr("HTTP Error {0}").format(response.status_code), "status": response.status_code}
            if not response.ok:
                 if 'message' not in response_data: response_data['message'] = response.text or self.tr("API Error {0}").format(response.status_code)
                 response_data.setdefault('status', response.status_code); print(f"API Error {response.status_code}: {response_data.get('message')}"); return None, response_data
            return response_data, None
        except requests.exceptions.RequestException as e: print(f"Network Error: {e}"); return None, {"message": self.tr("Network Error: {0}").format(e), "status": 500}
        except Exception as e: print(f"Unexpected Error: {e}\n{traceback.format_exc()}"); return None, {"message": self.tr("Unexpected Error: {0}").format(e), "status": 500}

    def login(self):
        if not self.username or not self.password: self.login_status.emit(False, self.tr("Username/Password missing.")); return
        endpoint = "login"; payload = {"username": self.username, "password": self.password}
        def _login_thread():
            data, error = self._make_request("POST", endpoint, data=payload)
            if error: self.logged_in = False; self.jwt_token = None; self.user_info = None; login_fail_msg = self.tr("Login failed ({0}): {1}").format(error.get('status', self.tr('N/A')), error.get('message', self.tr('Unknown error'))); self.login_status.emit(False, login_fail_msg)
            elif data and data.get("token"): self.logged_in = True; self.jwt_token = data["token"]; self.user_info = data.get("user"); print(f"Login OK. Level: {self.user_info.get('level', 'N/A')}, Allowed: {self.user_info.get('allowed_downloads', 'N/A')}"); self.login_status.emit(True, self.tr("Login successful."));
            if self.user_info: self.quota_info.emit(self.user_info.get('allowed_downloads', 0), self.user_info.get('allowed_downloads', 0))
            else: self.logged_in = False; self.jwt_token = None; self.user_info = None; self.login_status.emit(False, self.tr("Login failed: Invalid server response."))
        threading.Thread(target=_login_thread, daemon=True).start()

    def logout(self):
        if not self.jwt_token: return; endpoint = "logout"
        def _logout_thread(): _, error = self._make_request("DELETE", endpoint, requires_auth=True); self.logged_in = False; self.jwt_token = None; self.user_info = None;
        if error: print(f"Logout failed: {error.get('message', 'Unknown error')}")
        else: print("Logout successful.")
        threading.Thread(target=_logout_thread, daemon=True).start()

    # --- Corrected search_subtitles signature ---
    def search_subtitles(self, query=None, imdb_id=None, languages=None, tmdb_id=None, moviehash=None, season=None, episode=None, type=None): # Added 'type' parameter
        """
        Search for subtitles. At least one identifier is needed. Can specify type.
        """
        endpoint = "subtitles"; params = {}
        # Populate params dictionary
        if query: params['query'] = query
        if imdb_id: params['imdb_id'] = imdb_id.lower().replace('tt', '').lstrip('0')
        if tmdb_id: params['tmdb_id'] = tmdb_id
        if moviehash: params['moviehash'] = moviehash
        if languages: params['languages'] = languages.lower()
        if season is not None: params['season_number'] = season # API uses season_number
        if episode is not None: params['episode_number'] = episode # API uses episode_number
        if type: params['type'] = type # Pass type if provided ('movie' or 'episode')

        if not any([query, imdb_id, tmdb_id, moviehash]):
            self.search_error.emit(self.tr("Search requires an identifier (query, imdb_id, tmdb_id, or moviehash)."))
            return

        sorted_params = dict(sorted(params.items()))
        print(f"API Search Params: {sorted_params}") # Debug: Show what's sent

        def _search_thread():
            data, error = self._make_request("GET", endpoint, params=sorted_params)
            if error: search_fail_msg = self.tr("Search failed ({0}): {1}").format(error.get('status', self.tr('N/A')), error.get('message', self.tr('Unknown error'))); self.search_error.emit(search_fail_msg)
            elif data and 'data' in data:
                processed_results = []
                for item in data['data']:
                     # Data processing logic remains the same
                     attributes = item.get('attributes', {}); file_info = attributes.get('files', [{}])[0]; feature_details = attributes.get('feature_details', {})
                     processed = {'id': item.get('id'),'type': item.get('type'),'language': attributes.get('language'),'download_count': attributes.get('download_count'),'new_download_count': attributes.get('new_download_count'),'hearing_impaired': attributes.get('hearing_impaired'),'hd': attributes.get('hd'),'fps': attributes.get('fps'),'votes': attributes.get('votes'),'points': attributes.get('points'),'ratings': attributes.get('ratings'),'from_trusted': attributes.get('from_trusted'),'foreign_parts_only': attributes.get('foreign_parts_only'),'ai_translated': attributes.get('ai_translated'),'machine_translated': attributes.get('machine_translated'),'upload_date': attributes.get('upload_date'),'release': attributes.get('release'),'comments': attributes.get('comments'),'legacy_subtitle_id': attributes.get('legacy_subtitle_id'),'uploader': attributes.get('uploader', {}).get('name', 'Unknown'),'feature_title': feature_details.get('title', 'N/A'),'feature_year': feature_details.get('year'),'feature_imdb_id': feature_details.get('imdb_id'),'feature_tmdb_id': feature_details.get('tmdb_id'),'file_id': file_info.get('file_id'),'file_name': file_info.get('file_name', 'subtitle.srt')}
                     processed_results.append(processed)
                self.search_results.emit(processed_results)
            else:
                if data and data.get('total_count', 0) == 0: self.search_results.emit([])
                else: self.search_error.emit(self.tr("Search failed: Invalid response format."))
        threading.Thread(target=_search_thread, daemon=True).start()
    # --- End corrected signature ---

    def request_download(self, file_id):
        if not file_id: self.download_error.emit({"message": self.tr("File ID is required."), "status": 400}); return
        endpoint = "download"; payload = {"file_id": int(file_id)}
        login_potentially_required = bool(self.username and self.password)
        def _download_thread():
            data, error = self._make_request("POST", endpoint, data=payload, requires_auth=self.logged_in)
            if error: self.download_error.emit(error)
            elif data and data.get("link"):
                remaining = data.get('remaining', -1); print(f"Download link obtained. Remaining: {remaining}")
                self.download_ready.emit(data['link'], data.get('file_name', f'{file_id}.srt'))
            else: fallback_error = {"message": self.tr("Download failed: Invalid server response."), "status": 500}; self.download_error.emit(fallback_error)
        threading.Thread(target=_download_thread, daemon=True).start()

    def download_subtitle_file(self, download_link, save_path):
        try:
            response = requests.get(download_link, timeout=30, stream=True); response.raise_for_status()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                 for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            print(f"Subtitle downloaded: {save_path}"); return True, None
        except requests.exceptions.Timeout: error_msg = self.tr("Timeout downloading subtitle."); print(f"{error_msg} URL: {download_link}"); return False, error_msg
        except requests.exceptions.HTTPError as e: error_msg = self.tr("HTTP Error {0} downloading.").format(e.response.status_code); print(f"{error_msg} URL: {download_link} Details: {e.response.text}"); return False, error_msg
        except requests.exceptions.RequestException as e: error_msg = self.tr("Network error downloading: {0}").format(e); print(f"{error_msg} URL: {download_link}"); return False, error_msg
        except IOError as e: error_msg = self.tr("Failed write file {0}: {1}").format(save_path, e); print(error_msg); return False, error_msg
        except Exception as e: error_msg = self.tr("Unexpected error downloading file: {0}").format(e); print(f"{error_msg}\n{traceback.format_exc()}"); return False, error_msg

# --- END OF FILE source/subtitle_manager.py ---