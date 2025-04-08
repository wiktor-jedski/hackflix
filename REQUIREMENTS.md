# Raspberry Pi Movie Player App



## General description



An app that can be used to fetch movies and subtitles and generate voice-over based on .srt files. UI also includes suggestions tab based on previously liked movies.



### 1. Project overview and goals

   - App can play videos from local storage.

   - App can look for and download torrents of videos based on the movie name.

   - App can fetch subtitles for a given movie.

   - App can translate subtitles from English to Polish.

   - App can modify the audio of the movie by generating voice-over using TTS

   - App can handle rating movies and suggesting other movies based on ratings from IMDb



### 2. Hardware specifications

   - Raspberry Pi 5

   - Storage on external HDD

   - 1080p display

   - Audio output via HDMI



### 3. Software requirements

   - Raspberry Pi compliant OS (Raspbian or DietPi)

   - Media player software - probably VLC



### 4. UI requirements

   - GUI based

   - Able to navigate with a IR remote control with a keyboard that can be connected to Raspberry Pi

   - should be usable by non technical people



### 5. Feature requests

   - Library management (view, search, play, remove movies stored locally)

   - Download support (search for torrents based on movie name)

   - Subtitle support (search and download subtitles, translate using LLM)

   - Voiceover support (use subtitles to generate text to speech, mix into video)

   - Suggestions (rate movies, maybe possible to sync with existing IMDb account?)



### 6. Performance expectations

   - Supports up to 1080p



### 7. Development approach

   - Do not use existing software like Kodi

