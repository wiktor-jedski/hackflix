"""Tests for subtitle parser utility.

Tests cover:
- Valid SRT parsing
- Various timestamp/text formats
- Sound effect detection patterns
- Malformed SRT handling
- Empty file handling
"""

import pytest
from pathlib import Path

from src.utils.subtitle_parser import (
    SubtitleLine,
    SubtitleParseError,
    parse_srt_file,
    write_srt_file,
    merge_close_subtitles,
    _parse_timestamp,
    _format_timestamp,
    _is_sound_effect,
    _strip_html_tags,
)


class TestSubtitleLineDataclass:
    """Tests for SubtitleLine dataclass."""

    def test_subtitle_line_creation(self):
        """Verify SubtitleLine can be created with required fields."""
        line = SubtitleLine(
            index=1,
            start_ms=1000,
            end_ms=2000,
            text_source="Hello world",
        )
        assert line.index == 1
        assert line.start_ms == 1000
        assert line.end_ms == 2000
        assert line.text_source == "Hello world"
        assert line.text_translated == ""
        assert line.audio_clip_path == ""
        assert line.is_sound_effect is False

    def test_subtitle_line_with_all_fields(self):
        """Verify SubtitleLine with all fields populated."""
        line = SubtitleLine(
            index=5,
            start_ms=5000,
            end_ms=7000,
            text_source="Original text",
            text_translated="Translated text",
            audio_clip_path="/path/to/audio.mp3",
            is_sound_effect=True,
        )
        assert line.text_translated == "Translated text"
        assert line.audio_clip_path == "/path/to/audio.mp3"
        assert line.is_sound_effect is True

    def test_subtitle_line_defaults(self):
        """Verify SubtitleLine default values."""
        line = SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="Test")
        assert line.text_translated == ""
        assert line.audio_clip_path == ""
        assert line.is_sound_effect is False


class TestParseTimestamp:
    """Tests for _parse_timestamp function."""

    def test_parse_simple_timestamp(self):
        """Verify parsing of simple timestamp."""
        result = _parse_timestamp("00:00:01,500")
        assert result == 1500

    def test_parse_zero_timestamp(self):
        """Verify parsing of zero timestamp."""
        result = _parse_timestamp("00:00:00,000")
        assert result == 0

    def test_parse_one_hour(self):
        """Verify parsing of one hour timestamp."""
        result = _parse_timestamp("01:00:00,000")
        assert result == 3600000

    def test_parse_complex_timestamp(self):
        """Verify parsing of complex timestamp with milliseconds."""
        result = _parse_timestamp("02:15:30,250")
        expected = (2 * 3600 + 15 * 60 + 30) * 1000 + 250
        assert result == expected

    def test_parse_invalid_timestamp_format(self):
        """Verify error for invalid timestamp format."""
        with pytest.raises(SubtitleParseError) as exc_info:
            _parse_timestamp("invalid")
        assert "Invalid timestamp format" in str(exc_info.value)

    def test_parse_missing_milliseconds(self):
        """Verify error for timestamp without milliseconds."""
        with pytest.raises(SubtitleParseError) as exc_info:
            _parse_timestamp("00:00:00")
        assert "Invalid timestamp format" in str(exc_info.value)


class TestFormatTimestamp:
    """Tests for _format_timestamp function."""

    def test_format_zero_ms(self):
        """Verify formatting of zero milliseconds."""
        result = _format_timestamp(0)
        assert result == "00:00:00,000"

    def test_format_simple_ms(self):
        """Verify formatting of simple milliseconds."""
        result = _format_timestamp(1500)
        assert result == "00:00:01,500"

    def test_format_one_second(self):
        """Verify formatting of one second."""
        result = _format_timestamp(1000)
        assert result == "00:00:01,000"

    def test_format_complex_ms(self):
        """Verify formatting of complex milliseconds."""
        result = _format_timestamp(8150250)
        assert result == "02:15:50,250"

    def test_format_roundtrip(self):
        """Verify timestamp can be parsed and formatted back."""
        original = "02:15:30,250"
        ms = _parse_timestamp(original)
        result = _format_timestamp(ms)
        assert result == original


class TestIsSoundEffect:
    """Tests for _is_sound_effect function."""

    def test_bracket_sound_effect(self):
        """Verify bracket-enclosed text is detected as sound effect."""
        assert _is_sound_effect("[Door slams]") is True
        assert _is_sound_effect("[Music playing]") is True
        assert _is_sound_effect("[laughter]") is True

    def test_parenthesis_sound_effect(self):
        """Verify parenthesis-enclosed text is detected as sound effect."""
        assert _is_sound_effect("(Door slams)") is True
        assert _is_sound_effect("(Music playing)") is True
        assert _is_sound_effect("(sighs)") is True

    def test_not_sound_effect(self):
        """Verify normal text is not detected as sound effect."""
        assert _is_sound_effect("Hello world") is False
        assert _is_sound_effect("What time is it?") is False
        assert _is_sound_effect("") is False

    def test_partial_bracket(self):
        """Verify text with only opening bracket is not sound effect."""
        assert _is_sound_effect("[Door slams") is False
        assert _is_sound_effect("Door slams]") is False

    def test_whitespace_handling(self):
        """Verify whitespace is stripped before checking."""
        assert _is_sound_effect("  [Sound effect]  ") is True
        assert _is_sound_effect("  Normal text  ") is False


class TestStripHtmlTags:
    """Tests for _strip_html_tags function."""

    def test_strip_italic_tags(self):
        """Verify italic tags are removed."""
        assert _strip_html_tags("<i>Hello</i>") == "Hello"
        assert _strip_html_tags("<i>Multiple</i> <i>tags</i>") == "Multiple tags"

    def test_strip_bold_tags(self):
        """Verify bold tags are removed."""
        assert _strip_html_tags("<b>Bold text</b>") == "Bold text"

    def test_strip_underline_tags(self):
        """Verify underline tags are removed."""
        assert _strip_html_tags("<u>Underlined</u>") == "Underlined"

    def test_strip_font_tags(self):
        """Verify font tags with attributes are removed."""
        assert _strip_html_tags('<font color="red">Colored</font>') == "Colored"
        assert (
            _strip_html_tags('<font face="Arial" size="12">Styled</font>') == "Styled"
        )

    def test_strip_nested_tags(self):
        """Verify nested tags are all removed."""
        assert _strip_html_tags("<i><b>Nested</b></i>") == "Nested"

    def test_no_tags_unchanged(self):
        """Verify text without tags is unchanged."""
        assert _strip_html_tags("Plain text") == "Plain text"
        assert _strip_html_tags("") == ""

    def test_multiline_with_tags(self):
        """Verify multiline text with tags is handled."""
        text = "<i>Line one</i>\n<b>Line two</b>"
        assert _strip_html_tags(text) == "Line one\nLine two"

    def test_preserves_single_angle_bracket(self):
        """Verify single angle brackets are preserved."""
        assert _strip_html_tags("5 < 10") == "5 < 10"
        assert _strip_html_tags("10 > 5") == "10 > 5"

    def test_strip_self_closing_tags(self):
        """Verify self-closing tags are removed."""
        assert _strip_html_tags("Line<br/>break") == "Linebreak"
        assert _strip_html_tags("Line<br />break") == "Linebreak"


class TestParseSrtFile:
    """Tests for parse_srt_file function."""

    def test_parse_valid_srt_file(self, tmp_path: Path):
        """Verify parsing of valid SRT file."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
This is a test
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 2
        assert result[0].index == 1
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 4000
        assert result[0].text_source == "Hello world"
        assert result[1].index == 2
        assert result[1].start_ms == 5000
        assert result[1].end_ms == 8000
        assert result[1].text_source == "This is a test"

    def test_parse_srt_with_sound_effects(self, tmp_path: Path):
        """Verify sound effects are detected during parsing."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
[Door slams]

2
00:00:05,000 --> 00:00:08,000
Normal dialogue

3
00:00:09,000 --> 00:00:12,000
(Music playing)
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 3
        assert result[0].is_sound_effect is True
        assert result[1].is_sound_effect is False
        assert result[2].is_sound_effect is True

    def test_parse_empty_file(self, tmp_path: Path):
        """Verify parsing empty file returns empty list."""
        srt_file = tmp_path / "empty.srt"
        srt_file.write_text("")

        result = parse_srt_file(srt_file)

        assert result == []

    def test_parse_file_not_found(self):
        """Verify error when file does not exist."""
        non_existent = Path("/non/existent/file.srt")

        with pytest.raises(FileNotFoundError) as exc_info:
            parse_srt_file(non_existent)

        assert "not found" in str(exc_info.value)

    def test_parse_multiple_line_subtitle(self, tmp_path: Path):
        """Verify parsing of subtitle with multiple text lines."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Line one of dialogue
Line two of dialogue

2
00:00:05,000 --> 00:00:08,000
Single line
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 2
        assert result[0].text_source == "Line one of dialogue\nLine two of dialogue"
        assert result[1].text_source == "Single line"

    def test_parse_with_index_numbers(self, tmp_path: Path):
        """Verify parsing preserves index numbers."""
        srt_content = """42
00:00:01,000 --> 00:00:04,000
First subtitle

43
00:00:05,000 --> 00:00:08,000
Second subtitle
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert result[0].index == 42
        assert result[1].index == 43

    def test_parse_invalid_timestamp(self, tmp_path: Path):
        """Verify error for invalid timestamp in file."""
        srt_content = """1
invalid --> 00:00:04,000
Some text
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        with pytest.raises(SubtitleParseError) as exc_info:
            parse_srt_file(srt_file)

        assert "Invalid timestamp" in str(exc_info.value)

    def test_parse_handles_crlf_line_endings(self, tmp_path: Path):
        """Verify parsing handles Windows line endings."""
        srt_content = "1\r\n00:00:01,000 --> 00:00:04,000\r\nHello\r\n\r\n"
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 1
        assert result[0].text_source == "Hello"

    def test_parse_empty_lines_between_subtitles(self, tmp_path: Path):
        """Verify parsing handles multiple empty lines between subtitles."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle



2
00:00:05,000 --> 00:00:08,000
Second subtitle


"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 2

    def test_parse_strips_html_tags(self, tmp_path: Path):
        """Verify HTML tags are stripped from subtitle text."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
<i>Italic text</i>

2
00:00:05,000 --> 00:00:08,000
<b>Bold</b> and <u>underlined</u>

3
00:00:09,000 --> 00:00:12,000
<font color="yellow">Colored text</font>
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 3
        assert result[0].text_source == "Italic text"
        assert result[1].text_source == "Bold and underlined"
        assert result[2].text_source == "Colored text"

    def test_parse_unexpected_end_of_file(self, tmp_path: Path):
        """Verify error when file ends after index without timestamp."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

2"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        with pytest.raises(SubtitleParseError) as exc_info:
            parse_srt_file(srt_file)

        assert "Unexpected end of file" in str(exc_info.value)


class TestWriteSrtFile:
    """Tests for write_srt_file function."""

    def test_write_single_subtitle(self, tmp_path: Path):
        """Verify writing single subtitle to file."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello world",
            )
        ]
        output_path = tmp_path / "output.srt"

        write_srt_file(output_path, subtitles)

        content = output_path.read_text()
        assert "1" in content
        assert "00:00:01,000 --> 00:00:04,000" in content
        assert "Hello world" in content

    def test_write_translated_subtitle(self, tmp_path: Path):
        """Verify writing translated subtitles uses translated text."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello world",
                text_translated="Hola mundo",
            )
        ]
        output_path = tmp_path / "output.srt"

        write_srt_file(output_path, subtitles)

        content = output_path.read_text()
        assert "Hola mundo" in content

    def test_write_multiple_subtitles(self, tmp_path: Path):
        """Verify writing multiple subtitles."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=2000, end_ms=3000, text_source="Second"),
            SubtitleLine(index=3, start_ms=4000, end_ms=5000, text_source="Third"),
        ]
        output_path = tmp_path / "output.srt"

        write_srt_file(output_path, subtitles)

        content = output_path.read_text()
        assert content.count("-->") == 3
        assert "First" in content
        assert "Second" in content
        assert "Third" in content

    def test_write_empty_list(self, tmp_path: Path):
        """Verify writing empty list creates minimal file."""
        output_path = tmp_path / "empty.srt"

        write_srt_file(output_path, [])

        content = output_path.read_text()
        assert content == ""

    def test_write_multiline_subtitle(self, tmp_path: Path):
        """Verify writing subtitle with multiple lines."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Line one\nLine two\nLine three",
            )
        ]
        output_path = tmp_path / "output.srt"

        write_srt_file(output_path, subtitles)

        content = output_path.read_text()
        assert "Line one" in content
        assert "Line two" in content
        assert "Line three" in content

    def test_roundtrip_parsing_writing(self, tmp_path: Path):
        """Verify subtitles can be parsed and written back identically."""
        original_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
Second line
"""
        original_file = tmp_path / "original.srt"
        original_file.write_text(original_content)

        parsed = parse_srt_file(original_file)

        output_file = tmp_path / "output.srt"
        write_srt_file(output_file, parsed)

        reparsed = parse_srt_file(output_file)

        assert len(reparsed) == len(parsed)
        for orig, recon in zip(parsed, reparsed):
            assert orig.index == recon.index
            assert orig.start_ms == recon.start_ms
            assert orig.end_ms == recon.end_ms
            assert orig.text_source == recon.text_source

    def test_parse_skips_non_digit_lines(self, tmp_path: Path):
        """Verify parser skips lines that look like indices but aren't numbers."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

abc
00:00:05,000 --> 00:00:08,000
This line looks like an index but isn't numeric

2
00:00:09,000 --> 00:00:12,000
Third subtitle
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 2
        assert result[0].index == 1
        assert result[1].index == 2

    def test_parse_skips_lines_with_whitespace_before_number(self, tmp_path: Path):
        """Verify parser handles whitespace-prefixed numbers correctly."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

   3
00:00:05,000 --> 00:00:08,000
This line has whitespace prefix (treated as subtitle index 3)

2
00:00:09,000 --> 00:00:12,000
Third subtitle
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        result = parse_srt_file(srt_file)

        assert len(result) == 3
        assert result[0].index == 1
        assert result[1].index == 3
        assert result[2].index == 2

    def test_parse_raises_on_invalid_timestamp_line(self, tmp_path: Path):
        """Verify parser raises error when timestamp line is invalid."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

2
invalid_timestamp
Third subtitle
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content)

        with pytest.raises(SubtitleParseError) as exc_info:
            parse_srt_file(srt_file)

        assert "Invalid timestamp line" in str(exc_info.value)


class TestSubtitleParseError:
    """Tests for SubtitleParseError exception."""

    def test_error_is_exception_subclass(self):
        """Verify SubtitleParseError is an Exception subclass."""
        error = SubtitleParseError("Test error")
        assert isinstance(error, Exception)

    def test_error_message(self):
        """Verify error message is preserved."""
        error = SubtitleParseError("Custom error message")
        assert "Custom error message" in str(error)


class TestMergeCloseSubtitles:
    """Tests for merge_close_subtitles function."""

    def test_merge_empty_list(self):
        """Verify merging empty list returns empty list."""
        result = merge_close_subtitles([])
        assert result == []

    def test_merge_single_subtitle(self):
        """Verify single subtitle is returned unchanged."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="Hello")
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 1
        assert result[0].text_source == "Hello"

    def test_no_merge_when_gap_exceeds_threshold(self):
        """Verify subtitles with large gap are not merged."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=3000, end_ms=4000, text_source="Second"),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 2
        assert result[0].text_source == "First"
        assert result[1].text_source == "Second"

    def test_merge_when_gap_below_threshold(self):
        """Verify subtitles with small gap are merged."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=1500, end_ms=2500, text_source="Second"),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 1
        assert result[0].text_source == "First Second"
        assert result[0].start_ms == 0
        assert result[0].end_ms == 2500

    def test_merge_exactly_at_threshold(self):
        """Verify subtitles with gap equal to threshold are not merged."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=2000, end_ms=3000, text_source="Second"),
        ]
        result = merge_close_subtitles(subtitles, max_gap_ms=1000)
        assert len(result) == 2

    def test_merge_multiple_consecutive(self):
        """Verify multiple consecutive close subtitles are merged."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=1200, end_ms=2000, text_source="Second"),
            SubtitleLine(index=3, start_ms=2300, end_ms=3000, text_source="Third"),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 1
        assert result[0].text_source == "First Second Third"
        assert result[0].start_ms == 0
        assert result[0].end_ms == 3000

    def test_merge_reindexes_subtitles(self):
        """Verify merged subtitles are reindexed sequentially."""
        subtitles = [
            SubtitleLine(index=5, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=6, start_ms=1200, end_ms=2000, text_source="Second"),
            SubtitleLine(index=7, start_ms=5000, end_ms=6000, text_source="Third"),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 2
        assert result[0].index == 1
        assert result[1].index == 2

    def test_merge_preserves_translated_text(self):
        """Verify translated text is merged when present."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=1000,
                text_source="Hello",
                text_translated="Cześć",
            ),
            SubtitleLine(
                index=2,
                start_ms=1200,
                end_ms=2000,
                text_source="World",
                text_translated="Świat",
            ),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 1
        assert result[0].text_source == "Hello World"
        assert result[0].text_translated == "Cześć Świat"

    def test_merge_uses_source_when_translation_missing(self):
        """Verify source text is used when translation is missing for one line."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=1000,
                text_source="Hello",
                text_translated="Cześć",
            ),
            SubtitleLine(
                index=2,
                start_ms=1200,
                end_ms=2000,
                text_source="World",
                text_translated="",
            ),
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 1
        assert result[0].text_translated == "Cześć World"

    def test_merge_sound_effects_only_if_both_are(self):
        """Verify is_sound_effect is True only if both lines are sound effects."""
        # Both are sound effects
        subtitles_both = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=1000,
                text_source="[Door]",
                is_sound_effect=True,
            ),
            SubtitleLine(
                index=2,
                start_ms=1200,
                end_ms=2000,
                text_source="[Slam]",
                is_sound_effect=True,
            ),
        ]
        result_both = merge_close_subtitles(subtitles_both)
        assert result_both[0].is_sound_effect is True

        # Only one is sound effect
        subtitles_one = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=1000,
                text_source="[Door]",
                is_sound_effect=True,
            ),
            SubtitleLine(
                index=2,
                start_ms=1200,
                end_ms=2000,
                text_source="Hello",
                is_sound_effect=False,
            ),
        ]
        result_one = merge_close_subtitles(subtitles_one)
        assert result_one[0].is_sound_effect is False

    def test_merge_custom_gap_threshold(self):
        """Verify custom max_gap_ms parameter works."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="First"),
            SubtitleLine(index=2, start_ms=1400, end_ms=2000, text_source="Second"),
        ]
        # With default 1000ms, should merge (gap is 400ms)
        result_default = merge_close_subtitles(subtitles)
        assert len(result_default) == 1

        # With 300ms threshold, should not merge
        result_small = merge_close_subtitles(subtitles, max_gap_ms=300)
        assert len(result_small) == 2

    def test_merge_clears_audio_clip_path(self):
        """Verify merged subtitle has empty audio_clip_path."""
        subtitles = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=1000,
                text_source="First",
                audio_clip_path="/path/to/clip1.mp3",
            ),
            SubtitleLine(
                index=2,
                start_ms=1200,
                end_ms=2000,
                text_source="Second",
                audio_clip_path="/path/to/clip2.mp3",
            ),
        ]
        result = merge_close_subtitles(subtitles)
        assert result[0].audio_clip_path == ""

    def test_merge_mixed_gaps(self):
        """Verify correct behavior with mix of small and large gaps."""
        subtitles = [
            SubtitleLine(index=1, start_ms=0, end_ms=1000, text_source="A"),
            SubtitleLine(
                index=2, start_ms=1200, end_ms=2000, text_source="B"
            ),  # merge with A
            SubtitleLine(
                index=3, start_ms=5000, end_ms=6000, text_source="C"
            ),  # new group
            SubtitleLine(
                index=4, start_ms=6300, end_ms=7000, text_source="D"
            ),  # merge with C
            SubtitleLine(
                index=5, start_ms=10000, end_ms=11000, text_source="E"
            ),  # standalone
        ]
        result = merge_close_subtitles(subtitles)
        assert len(result) == 3
        assert result[0].text_source == "A B"
        assert result[1].text_source == "C D"
        assert result[2].text_source == "E"
