# --- START OF FILE source/torrent_manager.py ---

"""
Torrent manager module for the Raspberry Pi Movie Player App.
Provides functionality for searching, downloading, and managing torrents.
(Version compatible with older libtorrent bindings, e.g., <= 1.0.x)
"""

import os
import time
import threading
import re
from urllib.parse import quote_plus
import libtorrent as lt
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import traceback # Import traceback for detailed error logging

# Helper function to extract hash from magnet link
def extract_hash_from_magnet(magnet_link):
    match = re.search(r'urn:btih:([a-fA-F0-9]{40})', magnet_link)
    return match.group(1).lower() if match else None

class TorrentSearcher(QObject):
    """
    Class for searching torrents using a 1337x.to scraper.
    """

    search_completed = pyqtSignal(list)
    search_error = pyqtSignal(str) # Emits error string

    def __init__(self):
        super().__init__()
        self.base_url = "https://1337x.to"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def search(self, query, limit=10):
        threading.Thread(target=self._perform_search, args=(query, limit), daemon=True).start()

    def _perform_search(self, query, limit):
        try:
            results = self._search_1337x(query, limit)
            self.search_completed.emit(results)
        except requests.exceptions.RequestException as e:
            # Use self.tr() for user-facing error message part
            error_msg = self.tr("Network error during search: {0}").format(str(e))
            self.search_error.emit(error_msg)
        except Exception as e:
             # Use self.tr() for user-facing error message part
            error_msg = self.tr("Search error: {0}").format(str(e))
            print(f"{error_msg}\n{traceback.format_exc()}") # Keep detailed traceback for console
            self.search_error.emit(error_msg)

    def _search_1337x(self, query, limit):
        search_url = f"{self.base_url}/search/{quote_plus(query)}/1/"
        print(f"Searching URL: {search_url}") # Debug print

        try:
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            # Use self.tr() for exception message
            raise Exception(self.tr("Search request timed out."))
        except requests.exceptions.RequestException as e:
            # Use self.tr() for exception message
            raise Exception(self.tr("Failed to fetch search results: {0}").format(str(e)))

        soup = BeautifulSoup(response.content, 'lxml'); table = soup.find('table', class_='table-list')
        if not table: print("No results table found."); return []
        tbody = table.find('tbody');
        if not tbody: print("No tbody found."); return []
        rows = tbody.find_all('tr');
        if not rows: print("No result rows found."); return []
        print(f"Found {len(rows)} potential results.")

        results = []
        for row in rows[:limit * 2]:
            if len(results) >= limit: break
            try:
                cols = row.find_all('td')
                if len(cols) < 6: continue # Ensure enough columns
                name_col, seed_col, leech_col, _, size_col, _ = cols[:6]
                title_link_tag = name_col.find_all('a')[-1]; title = title_link_tag.text.strip()
                relative_url = title_link_tag['href']; detail_url = self.base_url + relative_url
                seeds = seed_col.text.strip(); peers = leech_col.text.strip(); size = size_col.contents[0].strip()
                print(f"Fetching details for: {title} from {detail_url}") # Debug
                try:
                    detail_response = requests.get(detail_url, headers=self.headers, timeout=10); detail_response.raise_for_status()
                    detail_soup = BeautifulSoup(detail_response.content, 'lxml')
                    magnet_link_tag = detail_soup.find('a', href=lambda href: href and href.startswith('magnet:?'))
                    if magnet_link_tag:
                        magnet_link = magnet_link_tag['href']; torrent_hash = extract_hash_from_magnet(magnet_link)
                        year_match = re.search(r'\(?(\d{4})\)?', title); year = int(year_match.group(1)) if year_match else None
                        quality_match = re.search(r'(720p|1080p|2160p|4K|WEB.?DL|BluRay|HDTV)', title, re.IGNORECASE)
                        quality = quality_match.group(1).upper() if quality_match else self.tr('Unknown') # Use tr() for Unknown
                        result_dict = {'title': title, 'year': year, 'quality': quality, 'size': size, 'seeds': int(seeds) if seeds.isdigit() else 0, 'peers': int(peers) if peers.isdigit() else 0, 'url': magnet_link, 'hash': torrent_hash, 'source': '1337x', 'image': '', 'rating': 0,}
                        results.append(result_dict); print(f"Added: {title}") # Debug
                    else: print(f"Magnet link not found for: {title}") # Debug
                except requests.exceptions.Timeout: print(f"Timeout details: {title}"); continue
                except requests.exceptions.RequestException as e: print(f"Error details: {title}: {e}"); continue
                except Exception as e: print(f"Error parsing details: {title}: {e}\n{traceback.format_exc()}"); continue
                time.sleep(0.1)
            except Exception as e: print(f"Error processing row: {e}\n{traceback.format_exc()}"); continue
        print(f"Returning {len(results)} final results.")
        return results[:limit]


class TorrentDownloader(QObject):
    """
    Class for downloading and managing torrents using libtorrent.
    """

    torrent_added = pyqtSignal(dict)
    torrent_updated = pyqtSignal(dict)
    torrent_completed = pyqtSignal(dict)
    # Emits: torrent_hash (str), error_message (str)
    torrent_error = pyqtSignal(str, str)

    def __init__(self, download_dir):
        super().__init__()
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        try:
            settings = {'listen_interfaces': '0.0.0.0:6881', 'user_agent': 'python_client/' + lt.version, 'announce_to_all_tiers': True, 'announce_to_all_trackers': True, 'enable_dht': True, 'enable_lsd': True, 'enable_upnp': True, 'enable_natpmp': True}
            self.session = lt.session(settings)
            self.session.listen_on(6881, 6891)
        except Exception as e:
             print(f"Warning: Could not initialize session with all settings: {e}. Using default session.")
             self.session = lt.session(); self.session.listen_on(6881, 6891)

        self.torrents = {}; self.running = True
        self.update_thread = threading.Thread(target=self._update_torrents_status, daemon=True); self.update_thread.start()

    def add_torrent(self, url, info_hash=None, title=None):
        if not url.startswith('magnet:'):
            # Use self.tr() for user-facing error message
            error_msg = self.tr("Failed to add torrent: Only magnet links are currently supported.")
            self.torrent_error.emit(info_hash or "", error_msg)
            return None

        derived_hash = extract_hash_from_magnet(url); effective_hash = info_hash or derived_hash
        try:
            params = lt.parse_magnet_uri(url); params.save_path = self.download_dir
            try: params.storage_mode = lt.storage_mode_t.storage_mode_sparse
            except AttributeError: print("Info: storage_mode_sparse not available."); pass
            if effective_hash and effective_hash in self.torrents: print(f"Torrent {effective_hash} already added."); return effective_hash
            handle = self.session.add_torrent(params); time.sleep(0.1); torrent_hash_actual = str(handle.info_hash())
            self.torrents[torrent_hash_actual] = {'handle': handle, 'hash': torrent_hash_actual, 'title': title or self.tr("Fetching metadata..."), 'added_time': datetime.now(), 'status': 'metadata', 'progress': 0, 'download_rate': 0, 'upload_rate': 0, 'num_peers': 0, 'total_size': 0, 'downloaded': 0, 'eta': 0, 'magnet_link': url} # Use tr() for placeholder
            print(f"Torrent added: {torrent_hash_actual}"); self.torrent_added.emit(self.torrents[torrent_hash_actual]); return torrent_hash_actual
        except RuntimeError as e:
            error_hash_report = effective_hash or "N/A"
            print(f"RuntimeError adding torrent: {str(e)}\n{traceback.format_exc()}")
            # Use self.tr() for user-facing error message format
            error_msg = self.tr("Failed to add torrent (runtime): {0}").format(str(e))
            self.torrent_error.emit(error_hash_report, error_msg)
            return None
        except Exception as e:
            error_hash_report = effective_hash or "N/A"
            print(f"Error adding torrent: {str(e)}\n{traceback.format_exc()}")
            # Use self.tr()
            error_msg = self.tr("Failed to add torrent: {0}").format(str(e))
            self.torrent_error.emit(error_hash_report, error_msg)
            return None

    def remove_torrent(self, torrent_hash, remove_files=False):
        if torrent_hash not in self.torrents: print(f"Torrent {torrent_hash} not found."); return False
        try:
            handle = self.torrents[torrent_hash]['handle']; flags = 1 if remove_files else 0
            print(f"Removing torrent {torrent_hash} flags: {flags}"); self.session.remove_torrent(handle, flags)
            if torrent_hash in self.torrents: del self.torrents[torrent_hash]
            print(f"Torrent {torrent_hash} removed."); return True
        except RuntimeError as e:
             print(f"RuntimeError removing: {str(e)}\n{traceback.format_exc()}")
             # Use self.tr()
             error_msg = self.tr("Failed to remove torrent (runtime): {0}").format(str(e))
             self.torrent_error.emit(torrent_hash, error_msg); return False
        except Exception as e:
            print(f"Error removing: {str(e)}\n{traceback.format_exc()}")
            # Use self.tr()
            error_msg = self.tr("Failed to remove torrent: {0}").format(str(e))
            self.torrent_error.emit(torrent_hash, error_msg); return False

    def pause_torrent(self, torrent_hash):
        if torrent_hash in self.torrents:
            try:
                handle = self.torrents[torrent_hash]['handle']; status = handle.status()
                if status.state in [lt.torrent_status.downloading, lt.torrent_status.finished, lt.torrent_status.seeding]:
                     handle.pause(); self.torrents[torrent_hash]['status'] = 'paused' # Keep status internal strings English
                     self.torrent_updated.emit(self.torrents[torrent_hash]); print(f"Torrent {torrent_hash} paused."); return True
                else: print(f"Cannot pause in state: {status.state}"); return False
            except RuntimeError as e:
                print(f"RuntimeError pausing: {e}\n{traceback.format_exc()}")
                # Use self.tr()
                error_msg = self.tr("Failed to pause torrent (runtime): {0}").format(e)
                self.torrent_error.emit(torrent_hash, error_msg); return False
            except Exception as e:
                print(f"Error pausing: {e}\n{traceback.format_exc()}")
                # Use self.tr()
                error_msg = self.tr("Failed to pause torrent: {0}").format(e)
                self.torrent_error.emit(torrent_hash, error_msg); return False
        return False

    def resume_torrent(self, torrent_hash):
        if torrent_hash in self.torrents:
            try:
                handle = self.torrents[torrent_hash]['handle']
                if handle.status().paused:
                     handle.resume(); self.torrents[torrent_hash]['status'] = 'downloading' # Keep status internal strings English
                     self.torrent_updated.emit(self.torrents[torrent_hash]); print(f"Torrent {torrent_hash} resumed."); return True
                else: print(f"Torrent {torrent_hash} not paused."); return False
            except RuntimeError as e:
                print(f"RuntimeError resuming: {e}\n{traceback.format_exc()}")
                 # Use self.tr()
                error_msg = self.tr("Failed to resume torrent (runtime): {0}").format(e)
                self.torrent_error.emit(torrent_hash, error_msg); return False
            except Exception as e:
                print(f"Error resuming: {e}\n{traceback.format_exc()}")
                 # Use self.tr()
                error_msg = self.tr("Failed to resume torrent: {0}").format(e)
                self.torrent_error.emit(torrent_hash, error_msg); return False
        return False

    def get_torrents(self):
        return list(self.torrents.values())

    def _update_torrents_status(self):
        lt_alert_wait_time = 1.0
        while self.running:
            try:
                 alerts = []
                 if hasattr(self.session, 'pop_alerts'):
                     if self.session.wait_for_alert(int(lt_alert_wait_time * 1000)): alerts = self.session.pop_alerts()
                 elif hasattr(self.session, 'pop_alert'):
                     while True: alert = self.session.pop_alert();
                     if not alert: break; alerts.append(alert)
                     if not alerts: time.sleep(lt_alert_wait_time)
                 for alert in alerts: self._handle_alert(alert)
                 for torrent_hash, torrent in list(self.torrents.items()):
                     if torrent_hash not in self.torrents: continue
                     self._update_single_torrent_status(torrent_hash, torrent)
            except RuntimeError as e: print(f"Libtorrent runtime error: {str(e)}\n{traceback.format_exc()}"); time.sleep(5)
            except Exception as e: print(f"Generic error in update loop: {str(e)}\n{traceback.format_exc()}"); time.sleep(5)

    def _handle_alert(self, alert):
        alert_type_name = type(alert).__name__
        handle = getattr(alert, 'handle', None); torrent_hash = None
        if handle and hasattr(handle, 'is_valid') and handle.is_valid():
             try: torrent_hash = str(handle.info_hash())
             except RuntimeError: handle = None

        if alert_type_name == 'metadata_received_alert':
            if handle and torrent_hash in self.torrents:
                torrent = self.torrents[torrent_hash];
                try:
                    ti = handle.get_torrent_info()
                    if ti is not None: torrent['title'] = ti.name(); torrent['total_size'] = ti.total_size()
                    print(f"Metadata received: {torrent['title']}"); self._update_single_torrent_status(torrent_hash, torrent)
                except RuntimeError as e: print(f"RuntimeError get_torrent_info: {e}")
        elif alert_type_name == 'torrent_finished_alert':
            if handle and torrent_hash in self.torrents:
                 torrent = self.torrents[torrent_hash]
                 if torrent['status'] not in ['seeding', 'error']: torrent['status'] = 'finished'
                 torrent['progress'] = 100.0; print(f"Torrent finished: {torrent['title']}")
                 self.torrent_completed.emit(torrent); self._update_single_torrent_status(torrent_hash, torrent)
        elif alert_type_name == 'torrent_error_alert':
             error_msg = self.tr("Unknown torrent error") # Use tr() for default
             if hasattr(alert, 'error') and hasattr(alert.error, 'message'): error_msg = alert.error.message()
             elif hasattr(alert, 'msg'): error_msg = alert.msg
             print(f"Torrent error alert: {error_msg}")
             if handle and torrent_hash in self.torrents:
                 self.torrents[torrent_hash]['status'] = 'error' # Keep internal status English
                 # Emit potentially translated generic message + specific error
                 full_error_msg = self.tr("Torrent error: {0}").format(error_msg)
                 self.torrent_error.emit(torrent_hash, full_error_msg)
             elif not handle: print(f"Torrent error alert invalid handle: {error_msg}")
        elif alert_type_name == 'stats_alert':
             if handle and torrent_hash in self.torrents: self._update_single_torrent_status(torrent_hash, self.torrents[torrent_hash])

    def _update_single_torrent_status(self, torrent_hash, torrent):
         try:
             handle = torrent['handle']
             if not hasattr(handle, 'is_valid') or not handle.is_valid(): print(f"Handle {torrent_hash} invalid."); return
             status = handle.status()
             if torrent['title'] == self.tr("Fetching metadata...") and handle.has_metadata(): # Check against translated placeholder
                 try:
                     ti = handle.get_torrent_info()
                     if ti: torrent['title'] = ti.name()
                 except RuntimeError:
                     pass
             if not torrent['total_size'] and status.total_wanted > 0: torrent['total_size'] = status.total_wanted
             torrent['progress'] = status.progress * 100; torrent['download_rate'] = status.download_payload_rate
             torrent['upload_rate'] = status.upload_payload_rate; torrent['num_peers'] = status.num_peers
             torrent['downloaded'] = status.total_done; torrent['num_seeds'] = status.num_seeds
             if status.download_payload_rate > 0 and status.progress < 1.0: remaining = status.total_wanted - status.total_wanted_done; torrent['eta'] = remaining / status.download_payload_rate if remaining > 0 else 0
             elif status.progress < 1.0: torrent['eta'] = float('inf')
             else: torrent['eta'] = 0

             current_state = status.state; is_paused = status.paused; is_finished = status.is_finished; is_seeding = status.is_seeding
             # Keep internal status strings English - UI layer can translate if needed
             if torrent['status'] == 'error': pass
             elif is_paused: torrent['status'] = 'paused'
             elif current_state == lt.torrent_status.checking_files: torrent['status'] = 'checking'
             elif current_state == lt.torrent_status.downloading_metadata: torrent['status'] = 'metadata'
             elif current_state == lt.torrent_status.downloading: torrent['status'] = 'downloading'
             elif current_state == lt.torrent_status.finished: torrent['status'] = 'finished'
             elif current_state == lt.torrent_status.seeding: torrent['status'] = 'seeding'
             elif current_state == lt.torrent_status.allocating: torrent['status'] = 'allocating'
             elif hasattr(lt.torrent_status, 'checking_resume_data') and current_state == lt.torrent_status.checking_resume_data: torrent['status'] = 'checking_resume'
             else:
                  if is_seeding: torrent['status'] = 'seeding'
                  elif is_finished: torrent['status'] = 'finished'
                  else: torrent['status'] = 'unknown'

             if is_seeding and torrent['status'] not in ['seeding', 'paused', 'error']: print(f"Correcting {torrent_hash} to seeding"); torrent['status'] = 'seeding'; torrent['progress'] = 100.0
             elif is_finished and torrent['status'] not in ['finished', 'seeding', 'paused', 'error']: print(f"Correcting {torrent_hash} to finished"); torrent['status'] = 'finished'; torrent['progress'] = 100.0
             self.torrent_updated.emit(torrent)
         except RuntimeError as e:
              print(f"Libtorrent runtime error update status {torrent_hash}: {e}\n{traceback.format_exc()}")
              if torrent_hash in self.torrents:
                    self.torrents[torrent_hash]['status'] = 'error'
                    # Use self.tr() for user-facing error
                    error_msg = self.tr("Status update error (runtime): {0}").format(str(e))
                    self.torrent_error.emit(torrent_hash, error_msg)
         except Exception as e:
             print(f"Generic error update status {torrent_hash}: {e}\n{traceback.format_exc()}")
             # Avoid emitting error for potentially transient issues unless critical

    def shutdown(self):
        # ... (Shutdown logic remains the same, mostly involves prints which stay English) ...
        print("Shutting down torrent manager..."); self.running = False
        if self.update_thread.is_alive(): print("Waiting update thread..."); self.update_thread.join(timeout=3);
        if self.update_thread.is_alive(): print("Warn: Update thread join timeout.")
        print(f"Pausing session...");
        try:
            self.session.pause()
            if hasattr(self.session, 'save_resume_data'): print("Saving resume data...");
            for torrent_hash, torrent in list(self.torrents.items()):
                 if torrent['handle'].is_valid() and torrent['handle'].has_metadata(): torrent['handle'].save_resume_data()
            time.sleep(2)
        except RuntimeError as e: print(f"RuntimeError shutdown pause/save: {e}")
        except Exception as e: print(f"Error shutdown pause/save: {e}")
        handles_to_remove = [t['handle'] for t in self.torrents.values() if hasattr(t['handle'],'is_valid') and t['handle'].is_valid()]
        self.torrents.clear(); print("Deleting libtorrent session...");
        try: del self.session
        except Exception as e: print(f"Error session deletion: {e}")
        print("Torrent manager shutdown complete.")

# (Example usage block removed as it's not part of the core library code)

# --- END OF FILE source/torrent_manager.py ---