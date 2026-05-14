# 07_DECISIONS.md

This document captures all architectural decisions made during the requirements interview.

---

## 1. Development Environment

| Decision | Choice | Rationale |
| :--- | :--- | :--- |
| Python version | 3.11.x (Bookworm default) | Single environment for dev and prod |
| Dev/Prod parity | Same environment | Avoid library incompatibilities |
| Virtual environment | `uv` | Modern, fast package management |

---

## 2. Core Technology Choices

| Component | Decision | Rejected Alternatives |
| :--- | :--- | :--- |
| Database | Raw `sqlite3` module | SQLAlchemy ORM |
| DB connections | Per-operation (open/close each time) | Connection pool, shared connection |
| Torrent client | Embedded `libtorrent` | qbittorrent-api, transmission-rpc |
| Torrent state | Persistent (save DHT, resume data) | Fresh each boot |
| TTS engine | `edge-tts` (online only) | gTTS, pyttsx3 (offline) |
| TTS voice | Hardcoded `pl-PL-MarekNeural` | User selectable |
| API keys | Environment variables | settings.json, encrypted storage |

---

## 3. Content Management

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Orphan policy | Keep indefinitely | Never auto-delete items removed from server |
| content.json version | Ignore field | Best-effort parsing, no strict validation |
| Poster caching | Cache on sync | Download all posters during content.json sync |
| Extra metadata | Display only if provided | No TMDB/IMDB enrichment |
| Video discovery | Largest file by size | Find video file in downloaded folder |

---

## 4. Season/Episode Handling

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Season pack structure | One magnet per season | Not one magnet per episode |
| Download priority | Sequential (E01 first) | Use libtorrent file prioritization |
| Episode playability | As available | Each episode playable when its file completes |

---

## 5. Subtitle & Translation

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Subtitle selection | Server specifies exact ID | No auto-search or user selection |
| Polish subs available | If `subtitle_id` + `translation_needed=false` | Skip translation step |
| Translation failure | Resume from failed batch | Track progress in DB per-batch |
| Sound effects in TTS | Skip entirely | Don't voice `[Door slams]` etc. |

---

## 6. Voiceover Pipeline

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Audio ducking | Required (full lector) | Dynamic duck with fade |
| Duck behavior | Fade down 0.3s before TTS, fade up 0.5s after | Not hard duck or sidechain |
| Audio extraction timing | During voiceover generation | Not on-the-fly during playback |
| TTS speedup limit | Max 1.3x | Faster sounds robotic |
| Timing drift limit | Max 5s cumulative | Clip to resync when exceeded |
| Voiceover storage | Permanent | Not regenerated on demand |
| Chunk cleanup | Always cleanup | Delete intermediates immediately |

---

## 7. UI/UX Decisions

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| UI language | Runtime switchable (EN/PL) | External .qm translation files |
| Breadcrumbs | No breadcrumbs | Clean UI, rely on Esc to navigate |
| Search filter | Persists after commit | Clear with Esc or new search |
| OSD content | Minimal icons only | No text/numbers |
| Toast notifications | Stack visually | Not queued sequentially |
| Player exit context | Return to exact state | Preserve drill-down navigation |
| Resume precision | To the second | Not millisecond, not scene |

---

## 8. Navigation & Input

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Key debounce | Per-key-type | Navigation repeats, actions debounced |
| App exit | Hidden Ctrl+Q | Not advertised in UI |
| Audio track cycling | All tracks individually | Not just original + voiceover |

---

## 9. Storage & Files

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Storage display | Lower of both (HDD + SD) | Show limiting factor |
| Delete scope | Files only, keep DB | Item can be re-downloaded |
| Custom subtitles | No, strict paths only | Only app-managed subtitles |
| Container formats | Trust VLC | No normalization |

---

## 10. Error Handling & Recovery

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Crash recovery | Auto-resume incomplete | Downloads and pipeline processing |
| Sync failure | Single attempt + error toast | No retry with backoff |
| HDD disconnect | Ignore until needed | Lazy error handling |
| Dependency check | Fail fast on startup | Don't gracefully degrade |
| Validation scope | Video + subtitles exist | Only selected episode for series |

---

## 11. System Integration

| Decision | Choice | Notes |
| :--- | :--- | :--- |
| Autostart | Not built-in | User configures manually |
| Updates | Manual only | No self-update mechanism |
| VLC on Pi 5 | Works with defaults | Hardware acceleration enabled |

---

## Summary of Major Changes from Original Docs

1. **SQLAlchemy replaced with raw sqlite3** - simpler, per-operation connections
2. **qbittorrent-api replaced with embedded libtorrent** - single process, tighter integration
3. **Season pack schema added** - magnet at season level, not episode level
4. **Full lector mode required** - not optional, includes audio ducking
5. **Translation is resumable** - batch progress tracking in DB
6. **API keys in environment variables** - not in settings.json
7. **5s timing drift limit** - clip to resync when exceeded
8. **External .qm files for i18n** - not compiled into binary
