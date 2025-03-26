"""
Torrent manager module for the Raspberry Pi Movie Player App.
Provides functionality for searching, downloading, and managing torrents.
"""

import os
import time
import threading
import libtorrent as lt
import requests
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

class TorrentSearcher(QObject):
    """
    Class for searching torrents from various public APIs.
    """
    
    search_completed = pyqtSignal(list)
    search_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.yts_api_url = "https://yts.mx/api/v2/list_movies.json"
    
    def search(self, query, limit=10):
        """
        Search for torrents using various APIs.
        Currently supports YTS API for movies.
        
        Args:
            query (str): Search query term
            limit (int): Maximum number of results to return
            
        Returns:
            None: Results are emitted via the search_completed signal
        """
        threading.Thread(target=self._perform_search, args=(query, limit), daemon=True).start()
    
    def _perform_search(self, query, limit):
        """
        Performs the actual search operation in a separate thread.
        
        Args:
            query (str): Search query term
            limit (int): Maximum number of results to return
        """
        try:
            results = []
            
            # Search YTS
            yts_results = self._search_yts(query)
            if yts_results:
                results.extend(yts_results[:limit])
            
            # Add more torrent search sources here as needed
            
            self.search_completed.emit(results)
        except Exception as e:
            self.search_error.emit(f"Search error: {str(e)}")
    
    def _search_yts(self, query):
        """
        Search the YTS API for movies.
        
        Args:
            query (str): Search query term
            
        Returns:
            list: List of torrent dictionaries with metadata
        """
        params = {
            'query_term': query,
            'limit': 20,
            'sort_by': 'download_count',
            'order_by': 'desc'
        }
        
        response = requests.get(self.yts_api_url, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        if data['status'] != 'ok' or data['data']['movie_count'] == 0:
            return []
        
        results = []
        for movie in data['data']['movies']:
            for torrent in movie['torrents']:
                result = {
                    'title': movie['title_long'],
                    'year': movie['year'],
                    'quality': torrent['quality'],
                    'size': torrent['size'],
                    'seeds': torrent['seeds'],
                    'peers': torrent['peers'],
                    'url': torrent['url'],
                    'hash': torrent['hash'],
                    'source': 'YTS',
                    'image': movie.get('medium_cover_image', ''),
                    'rating': movie.get('rating', 0),
                }
                results.append(result)
        
        return results


class TorrentDownloader(QObject):
    """
    Class for downloading and managing torrents using libtorrent.
    """
    
    # Signals for updating UI
    torrent_added = pyqtSignal(dict)
    torrent_updated = pyqtSignal(dict)
    torrent_completed = pyqtSignal(dict)
    torrent_error = pyqtSignal(str, str)  # hash, error message
    
    def __init__(self, download_dir):
        super().__init__()
        
        # Set up the download directory
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Initialize libtorrent session
        self.session = lt.session()
        self.session.listen_on(6881, 6891)
        
        # Dictionary to store torrent handles
        self.torrents = {}
        
        # Start the update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._update_torrents_status)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def add_torrent(self, url, info_hash=None, title=None):
        """
        Add a new torrent to download.
        
        Args:
            url (str): Magnet link or torrent URL
            info_hash (str, optional): Torrent info hash for identification
            title (str, optional): Title for the torrent
        
        Returns:
            str: Torrent hash if successful, None otherwise
        """
        try:
            # Different versions of libtorrent have different parameter names
            # Let's use a more compatible approach
            params = {
                'save_path': self.download_dir
            }

            # Try to set additional parameters based on what's available in this libtorrent version
            try:
                params['storage_mode'] = lt.storage_mode_t.storage_mode_sparse
            except:
                pass

            try:
                params['paused'] = False
            except:
                pass

            # Handle different libtorrent versions and their interfaces
            try:
                if url.startswith('magnet:'):
                    # This is a magnet link
                    handle = lt.add_magnet_uri(self.session, url, params)
                else:
                    # This is a torrent URL, download the .torrent file first
                    response = requests.get(url)

                    # Different versions of libtorrent have different ways to parse torrent files
                    try:
                        # Try newer API first
                        torrent_info = lt.torrent_info(lt.bdecode(response.content))
                        params['ti'] = torrent_info
                    except:
                        # Fall back to older API
                        params['info'] = lt.bdecode(response.content)

                    # Try different ways to add the torrent
                    try:
                        handle = self.session.add_torrent(params)
                    except:
                        # Some versions use this alternative method
                        atp = lt.add_torrent_params()
                        for k, v in params.items():
                            setattr(atp, k, v)
                        handle = self.session.add_torrent(atp)
            except Exception as e:
                self.torrent_error.emit(info_hash or "", f"Failed to add torrent: {str(e)}")
                return None

            # Wait for metadata if it's a magnet link
            if url.startswith('magnet:'):
                waiting_time = 0
                while not handle.has_metadata() and waiting_time < 60:
                    time.sleep(1)
                    waiting_time += 1

                if not handle.has_metadata():
                    self.torrent_error.emit(info_hash or str(handle.info_hash()), "Metadata timeout")
                    return None

            # Get the info hash for the torrent
            torrent_hash = str(handle.info_hash())

            # Store the torrent information
            self.torrents[torrent_hash] = {
                'handle': handle,
                'hash': torrent_hash,
                'title': title or handle.name(),
                'added_time': datetime.now(),
                'status': 'downloading',
                'progress': 0,
                'download_rate': 0,
                'upload_rate': 0,
                'num_peers': 0,
                'total_size': handle.status().total_wanted,
                'downloaded': 0,
                'eta': 0
            }

            # Emit the signal with initial torrent status
            self.torrent_added.emit(self.torrents[torrent_hash])

            return torrent_hash

        except Exception as e:
            self.torrent_error.emit(info_hash or "", f"Failed to add torrent: {str(e)}")
            return None

    def remove_torrent(self, torrent_hash, remove_files=False):
        """
        Remove a torrent from the session.

        Args:
            torrent_hash (str): Hash of the torrent to remove
            remove_files (bool): Whether to also delete downloaded files

        Returns:
            bool: True if successful, False otherwise
        """
        if torrent_hash not in self.torrents:
            return False

        try:
            self.session.remove_torrent(self.torrents[torrent_hash]['handle'],
                                      1 if remove_files else 0)
            del self.torrents[torrent_hash]
            return True
        except Exception as e:
            self.torrent_error.emit(torrent_hash, f"Failed to remove torrent: {str(e)}")
            return False

    def pause_torrent(self, torrent_hash):
        """Pause a torrent download"""
        if torrent_hash in self.torrents:
            self.torrents[torrent_hash]['handle'].pause()
            self.torrents[torrent_hash]['status'] = 'paused'
            self.torrent_updated.emit(self.torrents[torrent_hash])
            return True
        return False

    def resume_torrent(self, torrent_hash):
        """Resume a paused torrent download"""
        if torrent_hash in self.torrents:
            self.torrents[torrent_hash]['handle'].resume()
            self.torrents[torrent_hash]['status'] = 'downloading'
            self.torrent_updated.emit(self.torrents[torrent_hash])
            return True
        return False

    def get_torrents(self):
        """Get all torrents with their current status"""
        return list(self.torrents.values())

    def _update_torrents_status(self):
        """
        Continuously update torrent status in a background thread.
        """
        while self.running:
            for torrent_hash, torrent in list(self.torrents.items()):
                try:
                    handle = torrent['handle']
                    status = handle.status()

                    # Update torrent information
                    torrent['progress'] = status.progress * 100
                    torrent['download_rate'] = status.download_rate
                    torrent['upload_rate'] = status.upload_rate
                    torrent['num_peers'] = status.num_peers
                    torrent['downloaded'] = status.total_wanted_done

                    # Calculate ETA
                    if status.download_rate > 0:
                        remaining_bytes = status.total_wanted - status.total_wanted_done
                        torrent['eta'] = remaining_bytes / status.download_rate
                    else:
                        torrent['eta'] = 0

                    # Check if download is complete
                    if status.progress == 1.0 and torrent['status'] != 'finished':
                        torrent['status'] = 'finished'
                        self.torrent_completed.emit(torrent)

                    # Emit the updated torrent information
                    self.torrent_updated.emit(torrent)

                except Exception as e:
                    self.torrent_error.emit(torrent_hash, f"Status update error: {str(e)}")

            # Sleep to avoid excessive CPU usage
            time.sleep(1)

    def shutdown(self):
        """
        Clean shutdown of the torrent manager.
        Should be called when the application exits.
        """
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1)

        # Clean session
        for torrent in self.torrents.values():
            self.session.remove_torrent(torrent['handle'])
