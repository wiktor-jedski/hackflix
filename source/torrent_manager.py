# --- START OF FILE torrent_manager.py ---

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
    search_error = pyqtSignal(str)

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
            self.search_error.emit(f"Network error during search: {str(e)}")
        except Exception as e:
            self.search_error.emit(f"Search error: {str(e)}\n{traceback.format_exc()}") # Include traceback

    def _search_1337x(self, query, limit):
        search_url = f"{self.base_url}/search/{quote_plus(query)}/1/"
        print(f"Searching URL: {search_url}")

        try:
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception("Search request timed out.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch search results: {str(e)}")

        soup = BeautifulSoup(response.content, 'lxml')
        table = soup.find('table', class_='table-list')
        if not table:
            print("No results table found on page.")
            return []

        # Updated selector for tbody to be more robust
        tbody = table.find('tbody')
        if not tbody:
            print("No tbody found in table.")
            return []
        rows = tbody.find_all('tr')
        if not rows:
            print("No result rows found in table.")
            return []

        print(f"Found {len(rows)} potential results.")

        results = []
        for row in rows[:limit * 2]:
            if len(results) >= limit:
                 break

            try:
                cols = row.find_all('td')
                if len(cols) < 5: continue

                name_col, seed_col, leech_col, _, size_col, _ = cols[:6] # Unpack more carefully

                title_link_tag = name_col.find_all('a')[-1]
                title = title_link_tag.text.strip()
                relative_url = title_link_tag['href']
                detail_url = self.base_url + relative_url

                seeds = seed_col.text.strip()
                peers = leech_col.text.strip()
                size = size_col.contents[0].strip()

                print(f"Fetching details for: {title} from {detail_url}")
                try:
                    detail_response = requests.get(detail_url, headers=self.headers, timeout=10)
                    detail_response.raise_for_status()
                    detail_soup = BeautifulSoup(detail_response.content, 'lxml')

                    magnet_link_tag = detail_soup.find('a', href=lambda href: href and href.startswith('magnet:?'))

                    if magnet_link_tag:
                        magnet_link = magnet_link_tag['href']
                        torrent_hash = extract_hash_from_magnet(magnet_link)

                        year_match = re.search(r'\(?(\d{4})\)?', title)
                        year = int(year_match.group(1)) if year_match else None
                        quality_match = re.search(r'(720p|1080p|2160p|4K|WEB.?DL|BluRay|HDTV)', title, re.IGNORECASE)
                        quality = quality_match.group(1).upper() if quality_match else 'Unknown'

                        result_dict = {
                            'title': title, 'year': year, 'quality': quality, 'size': size,
                            'seeds': int(seeds) if seeds.isdigit() else 0,
                            'peers': int(peers) if peers.isdigit() else 0,
                            'url': magnet_link, 'hash': torrent_hash, 'source': '1337x',
                            'image': '', 'rating': 0,
                        }
                        results.append(result_dict)
                        print(f"Successfully added: {title}")
                    else:
                         print(f"Magnet link not found on detail page for: {title}")

                except requests.exceptions.Timeout:
                    print(f"Timeout fetching details for: {title}")
                    continue
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching details for {title}: {str(e)}")
                    continue
                except Exception as e:
                    print(f"Error parsing detail page for {title}: {str(e)}\n{traceback.format_exc()}") # Include traceback
                    continue

                time.sleep(0.1)

            except Exception as e:
                print(f"Error processing a search result row: {str(e)}\n{traceback.format_exc()}") # Include traceback
                continue

        print(f"Returning {len(results)} final results.")
        return results[:limit]


class TorrentDownloader(QObject):
    """
    Class for downloading and managing torrents using libtorrent.
    (Version compatible with older libtorrent bindings, e.g., <= 1.0.x)
    """

    torrent_added = pyqtSignal(dict)
    torrent_updated = pyqtSignal(dict)
    torrent_completed = pyqtSignal(dict)
    torrent_error = pyqtSignal(str, str)

    def __init__(self, download_dir):
        super().__init__()
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

        # Initialize libtorrent session (older style settings might be needed)
        try:
            # Older versions might need settings passed as a dictionary
            settings = {
                'listen_interfaces': '0.0.0.0:6881',
                'user_agent': 'python_client/' + lt.version, # Simple UA
                'announce_to_all_tiers': True,
                'announce_to_all_trackers': True,
                'enable_dht': True,
                'enable_lsd': True,
                'enable_upnp': True,
                'enable_natpmp': True
            }
            self.session = lt.session(settings)
            try:
                # Enable various status and error alerts
                alert_mask = (lt.alert.category_t.error_notification |
                              lt.alert.category_t.peer_notification |
                              lt.alert.category_t.port_mapping_notification |
                              lt.alert.category_t.storage_notification |
                              lt.alert.category_t.tracker_notification |
                              lt.alert.category_t.connect_notification |
                              lt.alert.category_t.status_notification |
                              # Add DHT specific alerts
                              lt.alert.category_t.dht_notification |
                              lt.alert.category_t.dht_log_notification |  # Very verbose
                              lt.alert.category_t.dht_operation_notification
                              )
                settings = self.session.get_settings()
                settings['alert_mask'] = alert_mask
                self.session.apply_settings(settings)
                print("Enabled detailed libtorrent alerts including DHT.")
            except AttributeError as e:
                print(
                    f"Warning: Could not set detailed alert mask (libtorrent version might be too old or flags changed): {e}")
            except Exception as e:
                print(f"Warning: Error setting alert_mask: {e}")

            # Also, ensure DHT is explicitly enabled (already done, but double-check)
            settings = self.session.get_settings()
            if 'enable_dht' not in settings or not settings['enable_dht']:
                settings['enable_dht'] = True
                self.session.apply_settings(settings)
                print("Ensured DHT is enabled.")
            settings[
                'dht_bootstrap_nodes'] = "dht.libtorrent.org:25401,router.utorrent.com:6881,router.bittorrent.com:6881,dht.transmissionbt.com:6881"
            self.session.apply_settings(settings)
            print("Set specific DHT bootstrap nodes.")

            # Listen on port
            self.session.listen_on(6881, 6891)

        except Exception as e:
             print(f"Warning: Could not initialize session with all settings: {e}. Using default session.")
             self.session = lt.session() # Fallback to default
             self.session.listen_on(6881, 6891)


        self.torrents = {}
        self.running = True
        self.update_thread = threading.Thread(target=self._update_torrents_status)
        self.update_thread.daemon = True
        self.update_thread.start()

    def add_torrent(self, url, info_hash=None, title=None):
        if not url.startswith('magnet:'):
            self.torrent_error.emit(info_hash or "", "Failed to add torrent: Only magnet links are currently supported.")
            return None

        derived_hash = extract_hash_from_magnet(url)
        effective_hash = info_hash or derived_hash

        try:
            params = lt.parse_magnet_uri(url)
            params.save_path = self.download_dir
            # storage_mode might not exist or have different values in older versions
            # Try setting it, but don't fail if it doesn't exist
            try:
                 params.storage_mode = lt.storage_mode_t.storage_mode_sparse
            except AttributeError:
                 print("Info: storage_mode_sparse not available in this libtorrent version.")
                 pass # Continue without setting storage mode if it fails

            if effective_hash and effective_hash in self.torrents:
                 print(f"Torrent with hash {effective_hash} already added.")
                 return effective_hash

            handle = self.session.add_torrent(params)
            # Wait briefly for the handle to potentially get the hash
            time.sleep(0.1)
            torrent_hash_actual = str(handle.info_hash())

            self.torrents[torrent_hash_actual] = {
                'handle': handle, 'hash': torrent_hash_actual,
                'title': title or "Fetching metadata...", 'added_time': datetime.now(),
                'status': 'metadata', 'progress': 0, 'download_rate': 0,
                'upload_rate': 0, 'num_peers': 0, 'total_size': 0,
                'downloaded': 0, 'eta': 0, 'magnet_link': url
            }
            print(f"Torrent added with hash: {torrent_hash_actual}")
            self.torrent_added.emit(self.torrents[torrent_hash_actual])
            return torrent_hash_actual

        except RuntimeError as e: # Catch RuntimeError for libtorrent issues
            error_hash_report = effective_hash if effective_hash else "N/A"
            print(f"RuntimeError adding torrent: {str(e)}\n{traceback.format_exc()}")
            self.torrent_error.emit(error_hash_report, f"Failed to add torrent (runtime): {str(e)}")
            return None
        except Exception as e: # Catch other potential errors
            error_hash_report = effective_hash if effective_hash else "N/A"
            print(f"Error adding torrent: {str(e)}\n{traceback.format_exc()}")
            self.torrent_error.emit(error_hash_report, f"Failed to add torrent: {str(e)}")
            return None


    def remove_torrent(self, torrent_hash, remove_files=False):
        if torrent_hash not in self.torrents:
             print(f"Torrent {torrent_hash} not found for removal.")
             return False
        try:
            handle = self.torrents[torrent_hash]['handle']
            # Older libtorrent uses integer flags for remove_torrent
            flags = 1 if remove_files else 0
            print(f"Removing torrent {torrent_hash} with flags: {flags}")
            self.session.remove_torrent(handle, flags)
            # Ensure key exists before deleting
            if torrent_hash in self.torrents:
                del self.torrents[torrent_hash]
            print(f"Torrent {torrent_hash} removed successfully.")
            return True
        except RuntimeError as e: # Catch RuntimeError
             print(f"RuntimeError removing torrent {torrent_hash}: {str(e)}\n{traceback.format_exc()}")
             self.torrent_error.emit(torrent_hash, f"Failed to remove torrent (runtime): {str(e)}")
             return False
        except Exception as e:
            print(f"Error removing torrent {torrent_hash}: {str(e)}\n{traceback.format_exc()}")
            self.torrent_error.emit(torrent_hash, f"Failed to remove torrent: {str(e)}")
            return False


    def pause_torrent(self, torrent_hash):
        if torrent_hash in self.torrents:
            try:
                handle = self.torrents[torrent_hash]['handle']
                status = handle.status()
                # Use older state constants and simplify condition
                if status.state == lt.torrent_status.downloading or status.state == lt.torrent_status.finished or status.state == lt.torrent_status.seeding:
                     handle.pause() # Simple pause call, no flags needed/available usually
                     self.torrents[torrent_hash]['status'] = 'paused'
                     self.torrent_updated.emit(self.torrents[torrent_hash])
                     print(f"Torrent {torrent_hash} paused.")
                     return True
                else:
                     print(f"Torrent {torrent_hash} cannot be paused in state: {status.state}")
                     return False
            except RuntimeError as e: # Catch RuntimeError
                print(f"RuntimeError pausing torrent {torrent_hash}: {e}\n{traceback.format_exc()}")
                self.torrent_error.emit(torrent_hash, f"Failed to pause (runtime): {e}")
                return False
            except Exception as e:
                print(f"Error pausing torrent {torrent_hash}: {e}\n{traceback.format_exc()}")
                self.torrent_error.emit(torrent_hash, f"Failed to pause: {e}")
                return False
        return False

    def resume_torrent(self, torrent_hash):
        if torrent_hash in self.torrents:
            try:
                handle = self.torrents[torrent_hash]['handle']
                if handle.status().paused:
                     handle.resume()
                     # Status will update on next cycle, or set tentatively
                     self.torrents[torrent_hash]['status'] = 'downloading' # Assume downloading
                     self.torrent_updated.emit(self.torrents[torrent_hash])
                     print(f"Torrent {torrent_hash} resumed.")
                     return True
                else:
                     print(f"Torrent {torrent_hash} is not paused.")
                     return False
            except RuntimeError as e: # Catch RuntimeError
                print(f"RuntimeError resuming torrent {torrent_hash}: {e}\n{traceback.format_exc()}")
                self.torrent_error.emit(torrent_hash, f"Failed to resume (runtime): {e}")
                return False
            except Exception as e:
                print(f"Error resuming torrent {torrent_hash}: {e}\n{traceback.format_exc()}")
                self.torrent_error.emit(torrent_hash, f"Failed to resume: {e}")
                return False
        return False

    def get_torrents(self):
        return list(self.torrents.values())

    def _update_torrents_status(self):
        lt_alert_wait_time = 1.0 # seconds

        while self.running:
            try:
                 # Process alerts (check if alert interface exists)
                 alerts = []
                 if hasattr(self.session, 'pop_alerts'): # Check for newer alert interface
                     if self.session.wait_for_alert(int(lt_alert_wait_time * 1000)):
                          alerts = self.session.pop_alerts()
                 elif hasattr(self.session, 'pop_alert'): # Check for older alert interface
                     while True:
                          alert = self.session.pop_alert()
                          if not alert: break
                          alerts.append(alert)
                     if not alerts: # If no alerts, wait a bit before next status check
                         time.sleep(lt_alert_wait_time)

                 for alert in alerts:
                     self._handle_alert(alert)

                 # Periodically update status for all torrents
                 for torrent_hash, torrent in list(self.torrents.items()):
                     if torrent_hash not in self.torrents: continue
                     self._update_single_torrent_status(torrent_hash, torrent)

            # --- Updated Exception Handling ---
            except RuntimeError as e: # Catch libtorrent runtime errors
                 print(f"Libtorrent runtime error in update loop: {str(e)}\n{traceback.format_exc()}")
                 time.sleep(5) # Avoid tight loop on error
            except Exception as e: # Catch other unexpected errors
                 print(f"Generic error in torrent status update loop: {str(e)}\n{traceback.format_exc()}")
                 time.sleep(5) # Avoid tight loop on error


    def _handle_alert(self, alert):
        alert_type_name = type(alert).__name__
        # print(f"Received alert: {alert_type_name}") # Less verbose default logging

        # Use hasattr to check for handle attribute safely
        handle = getattr(alert, 'handle', None)
        torrent_hash = None
        if handle and hasattr(handle, 'is_valid') and handle.is_valid():
             try:
                 torrent_hash = str(handle.info_hash())
             except RuntimeError: # Handle case where info_hash isn't ready
                 handle = None # Treat as invalid if hash fails

        # --- Metadata received alert ---
        # Older versions might use different alert names or structures
        if alert_type_name == 'metadata_received_alert':
            if handle and torrent_hash in self.torrents:
                torrent = self.torrents[torrent_hash]
                try:
                    ti = handle.get_torrent_info() # Older method name
                    if ti is not None:
                        torrent['title'] = ti.name()
                        torrent['total_size'] = ti.total_size()
                    print(f"Metadata received for {torrent_hash}: {torrent['title']}")
                    self._update_single_torrent_status(torrent_hash, torrent)
                except RuntimeError as e:
                     print(f"RuntimeError getting torrent info for {torrent_hash}: {e}")

        # --- Torrent finished alert ---
        elif alert_type_name == 'torrent_finished_alert':
            if handle and torrent_hash in self.torrents:
                 torrent = self.torrents[torrent_hash]
                 # Only mark as finished if not already seeding/error
                 if torrent['status'] not in ['seeding', 'error']:
                     torrent['status'] = 'finished'
                 torrent['progress'] = 100.0
                 print(f"Torrent finished: {torrent_hash} - {torrent['title']}")
                 self.torrent_completed.emit(torrent)
                 self._update_single_torrent_status(torrent_hash, torrent)

        # --- Torrent error alert ---
        elif alert_type_name == 'torrent_error_alert':
             error_msg = "Unknown error"
             if hasattr(alert, 'error') and hasattr(alert.error, 'message'):
                 error_msg = alert.error.message() # Try newer error structure
             elif hasattr(alert, 'msg'):
                 error_msg = alert.msg # Try older structure
             print(f"Torrent error alert: {error_msg}")
             if handle and torrent_hash in self.torrents:
                 self.torrents[torrent_hash]['status'] = 'error'
                 self.torrent_error.emit(torrent_hash, f"Torrent error: {error_msg}")
             elif not handle:
                 print(f"Torrent error alert for invalid/unknown handle: {error_msg}")


        # --- Stats alert ---
        elif alert_type_name == 'stats_alert':
             if handle and torrent_hash in self.torrents:
                 self._update_single_torrent_status(torrent_hash, self.torrents[torrent_hash])


    def _update_single_torrent_status(self, torrent_hash, torrent):
         try:
             handle = torrent['handle']
             if not hasattr(handle, 'is_valid') or not handle.is_valid():
                 print(f"Handle for {torrent_hash} is invalid, skipping update.")
                 return

             # Use status() method which exists in both old and new
             status = handle.status()

             # Update info from TorrentInfo if needed (older method name)
             if not torrent['title'] or torrent['title'] == "Fetching metadata...":
                 if handle.has_metadata():
                     try:
                         ti = handle.get_torrent_info()
                         if ti: torrent['title'] = ti.name()
                     except RuntimeError: pass # Ignore if info not ready
             if not torrent['total_size'] and status.total_wanted > 0:
                torrent['total_size'] = status.total_wanted


             # Update dynamic fields
             torrent['progress'] = status.progress * 100
             torrent['download_rate'] = status.download_payload_rate # Older versions use payload_rate
             torrent['upload_rate'] = status.upload_payload_rate
             torrent['num_peers'] = status.num_peers
             torrent['downloaded'] = status.total_done
             torrent['num_seeds'] = status.num_seeds

             # Calculate ETA
             if status.download_payload_rate > 0 and status.progress < 1.0:
                 remaining_bytes = status.total_wanted - status.total_wanted_done
                 torrent['eta'] = remaining_bytes / status.download_payload_rate if remaining_bytes > 0 else 0
             elif status.progress < 1.0:
                  torrent['eta'] = float('inf')
             else:
                 torrent['eta'] = 0

             # --- Update state string using older constants ---
             current_state = status.state
             is_paused = status.paused # Simple check
             is_finished = status.is_finished
             is_seeding = status.is_seeding

             # Don't overwrite error state unless explicitly resumed/cleared
             if torrent['status'] == 'error':
                  pass
             elif is_paused:
                 torrent['status'] = 'paused'
             # Check states using older constants directly under lt.torrent_status
             elif current_state == lt.torrent_status.checking_files:
                 torrent['status'] = 'checking'
             elif current_state == lt.torrent_status.downloading_metadata:
                 torrent['status'] = 'metadata'
             elif current_state == lt.torrent_status.downloading:
                 torrent['status'] = 'downloading'
             elif current_state == lt.torrent_status.finished:
                 torrent['status'] = 'finished'
             elif current_state == lt.torrent_status.seeding:
                 torrent['status'] = 'seeding'
             elif current_state == lt.torrent_status.allocating:
                 torrent['status'] = 'allocating'
             # checking_resume_data might not exist, map to checking
             elif hasattr(lt.torrent_status, 'checking_resume_data') and current_state == lt.torrent_status.checking_resume_data:
                  torrent['status'] = 'checking_resume'
             else:
                  # Fallback based on flags if state unknown
                  if is_seeding: torrent['status'] = 'seeding'
                  elif is_finished: torrent['status'] = 'finished'
                  else: torrent['status'] = 'unknown'


             # Correct status if libtorrent flags indicate completion/seeding
             if is_seeding and torrent['status'] not in ['seeding', 'paused', 'error']:
                  print(f"Correcting status for {torrent_hash} to seeding based on flag.")
                  torrent['status'] = 'seeding'
                  torrent['progress'] = 100.0
             elif is_finished and torrent['status'] not in ['finished', 'seeding', 'paused', 'error']:
                  print(f"Correcting status for {torrent_hash} to finished based on flag.")
                  torrent['status'] = 'finished'
                  torrent['progress'] = 100.0
                  # Re-emit completed signal if status changed to finished/seeding
                  # self.torrent_completed.emit(torrent)


             # Emit update signal
             self.torrent_updated.emit(torrent)

         # --- Updated Exception Handling ---
         except RuntimeError as e: # Catch libtorrent runtime errors specifically
              print(f"Libtorrent runtime error updating status for {torrent_hash}: {str(e)}\n{traceback.format_exc()}")
              # Mark as error to prevent repeated attempts on fatal handle issues
              if torrent_hash in self.torrents: # Check if removed concurrently
                    self.torrents[torrent_hash]['status'] = 'error'
                    self.torrent_error.emit(torrent_hash, f"Status update error (runtime): {str(e)}")
         except Exception as e: # Catch other unexpected errors
             print(f"Generic error updating status for {torrent_hash}: {str(e)}\n{traceback.format_exc()}")
             # Avoid marking as error for potentially transient issues


    def shutdown(self):
        print("Shutting down torrent manager...")
        self.running = False

        if self.update_thread.is_alive():
            print("Waiting for update thread to join...")
            self.update_thread.join(timeout=3)
            if self.update_thread.is_alive():
                print("Warning: Update thread did not join gracefully.")

        print(f"Pausing session...")
        try:
            self.session.pause()
             # Save resume data if method exists
            if hasattr(self.session, 'save_resume_data'):
                # This might be synchronous or asynchronous depending on version
                print("Saving resume data...")
                for torrent_hash, torrent in list(self.torrents.items()):
                     if torrent['handle'].is_valid() and torrent['handle'].has_metadata():
                          torrent['handle'].save_resume_data()
                # Wait for save_resume_data_alert (complex) or just wait a bit
                time.sleep(2) # Simple wait
        except RuntimeError as e:
             print(f"RuntimeError during session pause/save: {e}")
        except Exception as e:
             print(f"Error during session pause/save: {e}")


        handles_to_remove = [t['handle'] for t in self.torrents.values() if hasattr(t['handle'],'is_valid') and t['handle'].is_valid()]
        self.torrents.clear() # Clear internal dict

        # Explicitly remove handles (optional, session destructor might suffice)
        # print(f"Removing {len(handles_to_remove)} handles...")
        # for h in handles_to_remove:
        #    try:
        #        self.session.remove_torrent(h)
        #    except: pass # Ignore errors during cleanup

        print("Deleting libtorrent session...")
        try:
            del self.session # Explicitly trigger destructor
        except Exception as e:
            print(f"Error during session deletion: {e}")

        print("Torrent manager shutdown complete.")


# Example usage (for testing purposes)
if __name__ == '__main__':
    # (Keep the testing block as it was, it's useful for basic checks)
    searcher = TorrentSearcher()
    # ... rest of the testing code ...
    print("\n--- Downloader Test (Conceptual - Requires Manual Magnet) ---")
    temp_download_dir = os.path.join(os.path.expanduser("~"), "torrent_test_downloads")
    downloader = None
    try:
        downloader = TorrentDownloader(temp_download_dir)

        # You would typically connect signals here in a PyQt app
        # downloader.torrent_added.connect(...)
        # downloader.torrent_updated.connect(...)

        # Example: Add a known magnet link (replace with a valid one FOR TESTING ONLY)
        test_magnet = input("Enter a test magnet link (or leave blank to skip download test): ")
        if test_magnet.startswith("magnet:"):
            print(f"Adding test magnet to {temp_download_dir}")
            hash_added = downloader.add_torrent(test_magnet, title="Test Download")
            if hash_added:
                print(f"Added torrent with hash: {hash_added}")
                # Keep running to see progress updates
                try:
                    count = 0
                    while count < 60: # Run for ~5 minutes max
                        time.sleep(5)
                        torrents = downloader.get_torrents()
                        if torrents:
                            print("--- Status Update ---")
                            for t in torrents:
                                eta_str = f"{t['eta']:.0f}s" if t['eta'] != float('inf') else "inf"
                                print(f"{t['title']} - {t['status']} {t['progress']:.1f}% "
                                      f"DL:({t['download_rate']/1024:.1f} KB/s) UL:({t['upload_rate']/1024:.1f} KB/s) "
                                      f"ETA: {eta_str} P:{t['num_peers']} S:{t['num_seeds']}")
                        else:
                             print("No active torrents.")
                             break # Exit if torrent removed or never added properly
                        count += 1
                except KeyboardInterrupt:
                    print("Interrupt received...")
            else:
                print("Failed to add test magnet.")
        else:
            print("Skipping download test.")

    except Exception as e:
        print(f"Error during downloader test setup: {e}\n{traceback.format_exc()}")
    finally:
        if downloader:
            downloader.shutdown()
            print("Downloader shut down.")
