# --- START OF FILE source/translation_manager.py ---

"""
Handles subtitle translation using Google Gemini API.
Parses SRT, batches subtitle text entries, calls API, retries on errors,
falls back to single-entry translation, and reconstructs SRT.
"""

import os
import sys
import time
import threading
import re
import traceback
import requests
import json

# Try importing pysrt, provide fallback/warning if missing
try:
    import pysrt
    import chardet # pysrt often uses chardet
    PYSRT_AVAILABLE = True
except ImportError:
    print("WARNING: 'pysrt' or 'chardet' library not found. Subtitle parsing will be less robust.")
    print("Please install it: pip install pysrt chardet")
    PYSRT_AVAILABLE = False
    SRT_REGEX = re.compile(r"(\d+)\s*?\r?\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*?\r?\n(.*?)(?=\r?\n\r?\n\d+|\Z)", re.DOTALL | re.MULTILINE)


from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # Use the specific model identifier
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"
TARGET_LANGUAGE = "Polish"
TARGET_LANGUAGE_CODE = "pl" # Standard code for the target language
SOURCE_LANGUAGE = "English"
BATCH_SIZE = 10 # Number of SUBTITLE ENTRIES per batch.
API_RETRY_COUNT = 4 # Number of retries specifically for count mismatch
SINGLE_RETRY_COUNT = 1 # Number of retries for single line errors
API_TIMEOUT = 60 # Seconds

# Prompt for Batch Translation
PROMPT_TEMPLATE_BATCH = f"""MAKE SURE THAT THE NUMBER OF OUTPUTS EQUALS {{batch_size}}.
Translate the following {SOURCE_LANGUAGE} subtitle text entries into {TARGET_LANGUAGE}.
Each entry is separated by "|||". Some entries may contain multiple lines.
Preserve meaning and approximate line breaks if appropriate for {TARGET_LANGUAGE} subtitles.
Return the translated entries in the exact same order, also separated by "|||".
Do not add any extra text, explanations, numbering, or formatting. Only output the translated entries separated by "|||".

Input Entries (separated by |||):
>>>
{{batch_text}}
>>>

Translated Entries (separated by |||):
"""

# Prompt for Single Entry Translation
PROMPT_TEMPLATE_SINGLE = f"""Translate the following single {SOURCE_LANGUAGE} subtitle text entry into {TARGET_LANGUAGE}.
The entry may contain multiple lines.
Preserve the meaning and approximate line breaks if appropriate for {TARGET_LANGUAGE} subtitles.
Return only the translated text for this single entry. Do not add any extra text, explanations, or formatting.

Input Entry:
>>>
{{entry_text}}
>>>

Translated Entry:
"""
# --- End Configuration ---


class SubtitleTranslator(QObject):
    """
    Translates subtitle files entry-by-entry (batched) using the Gemini API,
    with fallback to single-entry translation.
    """
    translation_progress = pyqtSignal(int, int)
    translation_complete = pyqtSignal(str, str)
    translation_error = pyqtSignal(str, str) # Emits (original_srt_path, error_message_string)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = GEMINI_API_KEY
        self.api_url = GEMINI_API_URL
        self.session = requests.Session()

    def translate_srt_file(self, srt_filepath):
        """ Starts the translation process in a background thread. """
        if not os.path.exists(srt_filepath):
            # Use self.tr() for error message
            error_msg = self.tr("Input file not found: {0}").format(srt_filepath)
            self.translation_error.emit(srt_filepath, error_msg)
            return
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
             # Use self.tr()
             error_msg = self.tr("Gemini API Key not configured.")
             self.translation_error.emit(srt_filepath, error_msg)
             return
        thread = threading.Thread(target=self._run_translation, args=(srt_filepath,), daemon=True); thread.start()

    def _parse_srt(self, filepath):
        """ Parses SRT file using pysrt if available, otherwise basic regex. """
        print(f"Parsing SRT file: {filepath}"); subs = []; encoding = 'utf-8' # Debug print
        if PYSRT_AVAILABLE:
            try:
                with open(filepath, 'rb') as fp: raw_data = fp.read(); detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8') if detected else 'utf-8'
                if encoding.lower() in ['ascii','windows-1250','iso-8859-1','iso-8859-2']: encoding = 'utf-8'
                print(f"  Detected encoding: {encoding}"); subs = pysrt.open(filepath, encoding=encoding); print(f"  Parsed {len(subs)} entries using pysrt."); return subs
            except Exception as e: print(f"  pysrt failed (enc: {encoding}): {e}. Falling back."); # Debug print
        try: # Regex fallback
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            raw_entries = SRT_REGEX.findall(content); subs = []
            for index, start, end, text in raw_entries: subs.append({'index': int(index), 'start_time': start.strip(), 'end_time': end.strip(), 'text': text.strip().replace('\r', '')})
            print(f"  Parsed {len(subs)} entries using regex."); return subs # Debug print
        except Exception as e:
            print(f"  Regex parse failed: {e}") # Debug print
            # Use self.tr() for exception message
            raise ValueError(self.tr("Failed to parse SRT file ({0}) using both pysrt and regex.").format(filepath)) from e

    def _reconstruct_srt(self, original_subs, translated_texts, use_pysrt_obj):
        """ Reconstructs the SRT content string with translated text. """
        if len(original_subs) != len(translated_texts):
            print(f"Error: Sub count mismatch reconstruction. Orig: {len(original_subs)}, Trans: {len(translated_texts)}") # Debug print
            # Use self.tr() for exception message
            raise ValueError(self.tr("Subtitle count mismatch during reconstruction."))

        srt_content = ""
        if use_pysrt_obj:
            lines = []
            for i, sub in enumerate(original_subs): sub.text = translated_texts[i]; lines.append(str(i + 1)); lines.append(f"{sub.start} --> {sub.end}"); lines.append(sub.text); lines.append("")
            srt_content = "\n".join(lines)
        else:
            output_lines = [];
            for i, entry in enumerate(original_subs): output_lines.append(str(entry['index'])); output_lines.append(f"{entry['start_time']} --> {entry['end_time']}"); output_lines.append(translated_texts[i]); output_lines.append("")
            srt_content = "\n".join(output_lines)
        return srt_content

    def _call_gemini_api_single(self, entry_text, retry_count=SINGLE_RETRY_COUNT):
        """Sends a SINGLE entry to the Gemini API, with retries."""
        if not entry_text or not entry_text.strip(): return ""
        prompt = PROMPT_TEMPLATE_SINGLE.format(entry_text=entry_text)
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "candidateCount": 1}}
        params = {'key': self.api_key}
        for attempt in range(retry_count + 1):
             try:
                 response = self.session.post(self.api_url, headers=headers, params=params, json=payload, timeout=API_TIMEOUT)
                 response.raise_for_status(); data = response.json(); candidates = data.get('candidates', [])
                 if candidates:
                     content = candidates[0].get('content', {}); parts = content.get('parts', [])
                     if parts: return parts[0].get('text', '').strip()
                     # Use self.tr() for internal error messages that become exception text
                     else: raise ValueError(self.tr("Invalid Gemini response: 'parts' missing."))
                 else:
                     prompt_feedback = data.get('promptFeedback', {}); block_reason = prompt_feedback.get('blockReason')
                     if block_reason: raise ValueError(self.tr("Gemini API blocked prompt: {0}").format(block_reason))
                     else: raise ValueError(self.tr("Invalid Gemini response: 'candidates' missing."))
             except Exception as e:
                 print(f"      Single API Error (Attempt {attempt+1}/{retry_count+1}): {e}") # Debug print
                 if attempt == retry_count: print(f"      Single entry translation failed: '{entry_text[:50]}...'"); return entry_text # Fallback original
                 time.sleep(1.0 ** attempt) # Simple backoff
        return entry_text # Fallback if loop finishes unexpectedly

    def _call_gemini_api_batch(self, batch_entry_texts):
        """ Sends a batch of entries to Gemini API, retries on count mismatch, falls back to single. """
        if not batch_entry_texts: return []
        expected_count = len(batch_entry_texts); joined_batch_text = " ||| ".join(batch_entry_texts)
        prompt = PROMPT_TEMPLATE_BATCH.format(batch_text=joined_batch_text, batch_size=expected_count)
        headers = { 'Content-Type': 'application/json' }
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "candidateCount": 1}}
        params = { 'key': self.api_key }; last_error = None
        for attempt in range(API_RETRY_COUNT + 1):
            print(f"    Batch API Call Attempt {attempt + 1}/{API_RETRY_COUNT + 1}...") # Debug print
            try:
                response = self.session.post(self.api_url, headers=headers, params=params, json=payload, timeout=API_TIMEOUT)
                response.raise_for_status(); data = response.json(); candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {}); parts = content.get('parts', [])
                    if parts:
                        generated_text = parts[0].get('text', ''); translated_batch = [entry.strip() for entry in generated_text.split('|||')]
                        if len(translated_batch) == expected_count: print(f"    Attempt {attempt + 1}: Success (Count OK)."); return translated_batch # Debug print
                        else: print(f"    Attempt {attempt + 1}: API count mismatch! Exp:{expected_count}, Got:{len(translated_batch)}"); last_error = ValueError(self.tr("API translation count mismatch (Got {0}, Expected {1})").format(len(translated_batch), expected_count)) # Use tr()
                    # Use self.tr() for internal error messages
                    else: last_error = ValueError(self.tr("Invalid Gemini response: 'parts' missing."))
                else:
                     prompt_feedback = data.get('promptFeedback', {}); block_reason = prompt_feedback.get('blockReason')
                     if block_reason: last_error = ValueError(self.tr("Gemini API blocked prompt: {0}").format(block_reason)) # Use tr()
                     else: last_error = ValueError(self.tr("Invalid Gemini response: 'candidates' missing.")) # Use tr()
                if last_error and attempt < API_RETRY_COUNT: print(f"      Retrying batch... ({last_error})"); time.sleep(1.5 ** attempt); continue # Debug print
                else: print("      Max batch retries reached or structure error."); break # Debug print
            except requests.exceptions.RequestException as e: print(f"    Attempt {attempt + 1}: API Request Error: {e}"); last_error = e; time.sleep(1.5 ** attempt) # Debug print
            except Exception as e: print(f"    Attempt {attempt + 1}: Unexpected Error: {e}"); last_error = e; time.sleep(1.5 ** attempt) # Debug print
            if attempt == API_RETRY_COUNT: print("      Max batch retries reached."); break # Debug print

        # Use self.tr() for fallback message
        print(f"  Batch translation failed ({last_error}). Falling back to single entries...") # Debug print
        translated_batch_single = []
        for entry_index, original_text in enumerate(batch_entry_texts):
             print(f"    Translating entry {entry_index+1}/{len(batch_entry_texts)} individually...") # Debug print
             translated_text = self._call_gemini_api_single(original_text); translated_batch_single.append(translated_text)
        if len(translated_batch_single) != expected_count:
             # Use self.tr() for error message
             print(f"  ERROR: Count mismatch after single fallback! Returning original."); return batch_entry_texts # Debug print
        return translated_batch_single


    def _run_translation(self, srt_filepath):
        """ The actual translation logic running in a background thread. """
        try:
            original_subs = self._parse_srt(srt_filepath)
            is_pysrt_obj = PYSRT_AVAILABLE and isinstance(original_subs, pysrt.SubRipFile)
            all_original_texts = [sub.text_without_tags if is_pysrt_obj else entry['text'] for sub in original_subs] if is_pysrt_obj else [entry['text'] for entry in original_subs]
            total_entries = len(all_original_texts)
            if total_entries == 0: raise ValueError(self.tr("SRT file has no text entries.")); # Use tr()

            all_translated_texts = []; total_batches = (total_entries + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"Starting translation of {total_entries} entries in {total_batches} batches...") # Debug print

            for i in range(0, total_entries, BATCH_SIZE):
                batch_num = (i // BATCH_SIZE) + 1
                print(f"  Translating Batch {batch_num}/{total_batches}...") # Debug print
                self.translation_progress.emit(batch_num, total_batches)
                batch_to_translate = all_original_texts[i : i + BATCH_SIZE]
                translated_batch = self._call_gemini_api_batch(batch_to_translate)
                all_translated_texts.extend(translated_batch)

            print("Translation processing complete. Reconstructing file...") # Debug print
            translated_srt_content = self._reconstruct_srt(original_subs, all_translated_texts, is_pysrt_obj)

            dir_name = os.path.dirname(srt_filepath); base_name_full = os.path.basename(srt_filepath)
            base_name_no_ext, ext = os.path.splitext(base_name_full)
            lang_pattern = r'\.([a-zA-Z]{2,3})$'; match = re.search(lang_pattern, base_name_no_ext)
            video_base_name = base_name_no_ext
            if match: lang_code_found = match.group(1); print(f"  Found lang code '.{lang_code_found}'."); video_base_name = base_name_no_ext[:-len(match.group(0))] # Debug print
            translated_srt_filename = f"{video_base_name}.{TARGET_LANGUAGE_CODE}{ext}"; translated_srt_path = os.path.join(dir_name, translated_srt_filename)

            try: # Save the file
                with open(translated_srt_path, "w", encoding="utf-8") as f: f.write(translated_srt_content)
                print(f"Saved translated file: {translated_srt_path}") # Debug print
                self.translation_complete.emit(srt_filepath, translated_srt_path)
            except IOError as e:
                 # Use self.tr() for exception message
                 raise IOError(self.tr("Failed write translated file '{0}': {1}").format(translated_srt_path, e))

        except Exception as e:
            print(f"Error during translation for {srt_filepath}: {e}"); traceback.print_exc() # Debug print
            # Emit the potentially translated exception message
            self.translation_error.emit(srt_filepath, str(e))

# --- END OF FILE source/translation_manager.py ---