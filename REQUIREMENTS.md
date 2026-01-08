# Raspberry Pi Movie Player App



## General description



An app that can be used to fetch movies and series and their subtitles and generate voice-over based on .srt files. 
Movies and subtitles metadata is served by a server.



### 1. Project overview and goals

   - App can play videos from local storage.

   - App can download movies and series and their subtitles that are defined in the .json file fetched from server

   - App can translate subtitles from English to Polish if metadata specifies that translation is needed.

   - App can modify the audio of the movie by generating voice-over using TTS


### 2. Hardware specifications

   - Raspberry Pi 5

   - Storage on external HDD and internal drive

   - 1080p display

   - Audio output via HDMI



### 3. Software requirements

   - Raspberry Pi compliant OS (Raspbian or DietPi)

   - Media player software - probably VLC



### 4. UI requirements

   - GUI based

   - Able to navigate with a handheld keyboard that can be connected to Raspberry Pi

   - should be usable by non technical people

   - Using mouse is limited - user can freely browse items using keyboard, switch movies/series tabs with Tab, trigger search with s, delete items with d, sync with server with p, Enter to confirm, Esc to cancel



### 5. Feature requests

   - Library management (view, search, play/start download, delete)

   - Download support (uses magnet link in metadata to download)

   - Subtitle support (uses OpenSubtitles API and subtitle ID for getting subtitles, Gemini API for translation)

   - Voiceover support (use subtitles to generate text to speech, mix into video) - developed at the very end, needs to be researched



### 6. Performance expectations

   - Supports up to 1080p



### 7. Development approach

   - Do not use existing software like Kodi

