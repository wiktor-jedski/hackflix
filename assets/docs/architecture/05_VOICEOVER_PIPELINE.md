# 05_VOICEOVER_PIPELINE.md

## 1. The Pipeline Overview

The pipeline runs in a background `QThread` (PipelineService). It is triggered automatically when a download completes if `subtitle_id` is not null.

**Phases:**
1.  **Extraction/Fetching:** Get the source `.srt` file using server-specified OpenSubtitles ID.
2.  **Translation:** Batch-process text through Gemini API to get Polish text ONLY IF `translation_needed = True`. **Resumable on failure.**
3.  **Audio Generation (TTS):** Convert text to audio clips using `edge-tts` (online only, `pl-PL-MarekNeural`).
4.  **Audio Extraction:** Extract original audio from video file for ducking.
5.  **Dynamic Ducking:** Apply fade-based ducking to original audio when TTS speaks.
6.  **Time-Stretch & Stitching:** Fit TTS audio into subtitle time slots (max 1.3x speedup, max 5s cumulative drift).
7.  **Final Mix:** Combine ducked original audio with TTS into lector-style voiceover.
8.  **Storage:** Store final voiceover permanently (not regenerated).

---

## 2. Step 1: Subtitle Acquisition

The server specifies an exact OpenSubtitles ID in `content.json`. If `subtitle_id` is `null`, the entire pipeline is skipped.

*   **Library:** `python-opensubtitles` or direct REST API requests.
*   **Action:** Download `.srt` file to `{movie_folder}/original.srt` using the server-specified ID.
*   **Logic:**
    *   If `subtitle_id` exists AND `translation_needed = false` → Polish subtitles are directly available.
    *   If `subtitle_id` exists AND `translation_needed = true` → English subtitles, need translation.
*   **Parsing:** Parse `.srt` into a structured list of objects:
    ```python
    @dataclass
    class SubtitleLine:
        index: int
        start_ms: int
        end_ms: int
        text_source: str
        text_translated: str = ""
        audio_clip_path: str = ""
        is_sound_effect: bool = False  # True if text matches pattern like [Door slams]
    ```

---

## 3. Step 2: Translation (Gemini API)

We cannot send lines one by one (too slow, hits rate limits). We must **batch** them.
**This step is skipped if `translation_needed = false` (Polish subtitles directly available).**

*   **Batch Size:** ~20-50 lines per API call.
*   **Prompt Strategy:** structured JSON-to-JSON transformation to ensure line counts match.

**System Prompt:**
> "You are a professional subtitle translator. Translate the following JSON list of English movie subtitles into Polish. Maintain the tone and context. Do not translate sound effects (e.g., [Door bangs]). Return ONLY the JSON."

**User Prompt:**
```json
[
  {"id": 1, "text": "Hello there."},
  {"id": 2, "text": "General Kenobi!"}
]
```

**Output Handling:**
*   Validate that the number of returned lines matches the input.
*   Save the result to `{movie_folder}/pl.srt`.

**Failure Recovery (Resumable Translation):**
*   Track progress in `translation_progress` table: `last_completed_batch`, `total_batches`.
*   On API failure (rate limit, network error), pipeline pauses.
*   On retry, **resume from the last successful batch** instead of starting over.
*   Only delete progress tracking after full translation success.

---

## 4. Step 3: TTS & Audio Alignment (The "Engine")

This is the most critical logic. We need to generate audio that fits strictly within the `start_ms` and `end_ms` of the subtitle.

**Prerequisite:** TTS requires internet connection (`edge-tts` is online only). No offline fallback.

### 4.1. Text-to-Speech Generation
*   **Engine:** `edge-tts` (Microsoft Edge Online TTS - higher quality, free).
*   **Voice:** Hardcoded `pl-PL-MarekNeural` (Polish male neural voice).
*   **Process:** Generate a temporary `.mp3` file for every single subtitle line.
*   **Skip Sound Effects:** Lines matching patterns like `[Door slams]`, `(Music playing)`, etc. are skipped entirely (no TTS generated).

### 4.2. Duration Check & Time Stretching with Drift Tracking
*   **Cumulative Drift Tracking:** Track total timing drift across all lines. Maximum allowed: **5 seconds**.
*   **Logic:**
    1.  Measure duration of `temp_line_X.mp3`.
    2.  Calculate `slot_duration = start_ms_X+1 - start_ms_X - 0.3`.
    3.  **If `audio_duration > slot_duration`**:
        *   Calculate speedup factor: `factor = audio_duration / slot_duration`.
        *   Cap max speedup at 1.3x (anything faster sounds robotic).
        *   If it still doesn't fit after 1.3x:
            *   Calculate overflow = `audio_duration / 1.3 - slot_duration`.
            *   Add overflow to cumulative drift.
            *   **If cumulative drift > 5s:** Clip TTS audio to fit slot (accept cut-off speech to resync).
            *   **If cumulative drift <= 5s:** Accept overlap, delay next line start.
        *   Apply `ffmpeg` filter: `atempo=factor`.
    4.  **If `audio_duration < slot_duration`**:
        *   Align to start. No stretching needed.
        *   Reduce cumulative drift by unused slot time (helps recover from earlier delays).
    5.  Special case for last line (no next line): align temp_line_X.mp3 to start_ms.

---

## 5. Step 4: Audio Extraction & Dynamic Ducking (Full Lector Mode)

**REQUIRED:** Full lector mode with original audio ducked underneath the voiceover.

### 5.1. Original Audio Extraction
*   Extract the audio track from the video file using `ffmpeg`.
*   This happens during voiceover generation (not on-the-fly during playback).
*   Output: `{movie_folder}/original_audio.wav`

### 5.2. Dynamic Ducking with Fade
When TTS is speaking, the original audio volume reduces. Between dialogue, it comes back up.

*   **Duck Level:** Reduce original to ~20% volume during TTS.
*   **Fade Duration:** ~0.3-0.5 seconds fade down when TTS starts, ~0.5 seconds fade up after TTS ends.
*   **Implementation:** Create a volume envelope based on subtitle timestamps:
    ```
    For each subtitle line:
      - Fade down original audio starting 0.3s before TTS start
      - Keep ducked during TTS
      - Fade up 0.5s after TTS ends
    ```

---

## 6. Step 5: Final Stitching (FFmpeg/Pydub)

We will construct a single long audio file (`voiceover_pl.wav`) that matches the length of the movie.

**Approach:**
We cannot run 1000 ffmpeg commands. We must generate a complex "filter complex" command or use a python library like `pydub`.

**Full Lector Mix Process (Pydub):**
```python
from pydub import AudioSegment

# 1. Load extracted original audio (already processed for ducking)
original_ducked = AudioSegment.from_file("original_audio_ducked.wav")

# 2. Create TTS track
tts_track = AudioSegment.silent(duration=movie_total_duration_ms)

for line in subtitles:
    if line.is_sound_effect:
        continue  # Skip sound effects
    clip = AudioSegment.from_file(line.audio_clip_path)
    tts_track = tts_track.overlay(clip, position=line.start_ms)

# 3. Mix ducked original with TTS (TTS on top at full volume)
final_track = original_ducked.overlay(tts_track)

# Export
final_track.export("voiceover_pl.wav", format="wav")
```

**Optimization for Pi 5:**
Doing this for a 2-hour movie requires massive RAM.
**Chunking Strategy:**
1.  Process the movie in 10-minute chunks.
2.  Generate `part_01.wav`, `part_02.wav`...
3.  Concatenate chunks at the end using `ffmpeg concat`.
4.  **Always cleanup:** Delete intermediate chunk files immediately after final merge.

---

## 7. Playback Integration (VLC)

Once `voiceover_pl.wav` is generated (includes ducked original audio + TTS):

1.  **VLC Argument:**
    When loading the video:
    ```python
    instance = vlc.Instance()
    player = instance.media_player_new()
    media = instance.media_new(video_path)

    # Add the external audio file as a slave (synchronous extra track)
    # 'input-slave' tells VLC to play this file in parallel
    media.add_option(f"input-slave={voiceover_path}")

    player.set_media(media)
    player.play()
    ```

2.  **Audio Track Selection:**
    *   VLC will see the video's internal audio track(s) and the slave audio (voiceover).
    *   User cycles through **all tracks individually** using the L key (e.g., English → Spanish → Voiceover).
    *   Since voiceover already includes ducked original audio, no additional mixing needed during playback.

3.  **Voiceover Storage:**
    *   Voiceover files are stored **permanently** (not regenerated on demand).
    *   Typical size: ~600MB for a 2-hour movie at CD quality.

---

## 8. Error Handling

*   **API Quotas:** Gemini has limits. If limit hit, pause pipeline. **Translation is resumable** - tracks batch progress in DB.
*   **Sound Effects:** Lines matching `[...]` or `(...)` patterns are skipped (no TTS).
*   **Empty Subs:** If a line is just "..." or empty, skip TTS.
*   **Cleanup:** Delete all temporary `.mp3` clips **immediately** after final WAV is generated.
*   **Crash Recovery:** On app restart, automatically resume any incomplete pipeline processing.
