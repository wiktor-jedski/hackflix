"""Helpers for finding OpenSubtitles matches for catalog entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_LANGUAGES = ("pl", "en")


@dataclass(frozen=True)
class CatalogTarget:
    """Catalog item or episode needing subtitles."""

    item: dict[str, Any]
    subtitle_holder: dict[str, Any]
    media_type: str
    title: str
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None


@dataclass(frozen=True)
class SubtitleCandidate:
    """Ranked subtitle candidate from OpenSubtitles."""

    result_id: str
    file_id: int
    language: str
    score: int
    release: str
    download_count: int
    new_download_count: int
    ratings: float
    from_trusted: bool
    moviehash_match: bool


def iter_catalog_targets(catalog: dict[str, Any]) -> list[CatalogTarget]:
    """Return movies and episodes from a catalog in update order."""
    targets: list[CatalogTarget] = []
    for item in catalog.get("items", []):
        item_type = item.get("type")
        title = str(item.get("title", "")).strip()
        if item_type == "movie":
            targets.append(
                CatalogTarget(item=item, subtitle_holder=item, media_type="movie", title=title)
            )
            continue

        if item_type != "series":
            continue

        for season in item.get("seasons", []):
            season_number = _optional_int(season.get("season_number"))
            for episode in season.get("episodes", []):
                episode_number = _optional_int(episode.get("number"))
                targets.append(
                    CatalogTarget(
                        item=item,
                        subtitle_holder=episode,
                        media_type="episode",
                        title=title,
                        season_number=season_number,
                        episode_number=episode_number,
                        episode_title=episode.get("title"),
                    )
                )
    return targets


def target_label(target: CatalogTarget) -> str:
    """Return a display label for a catalog target."""
    if target.media_type == "movie":
        return target.title

    season = target.season_number or 0
    episode = target.episode_number or 0
    return f"{target.title} S{season:02d}E{episode:02d} {target.episode_title or ''}".strip()


def build_search_params(
    target: CatalogTarget, language: str, include_fallback_query: bool = True
) -> dict[str, Any]:
    """Build OpenSubtitles search params for a catalog target."""
    params: dict[str, Any] = {
        "languages": language,
        "type": target.media_type,
        "hearing_impaired": "exclude",
        "foreign_parts_only": "exclude",
        "machine_translated": "exclude",
        "ai_translated": "exclude",
    }

    if target.media_type == "movie":
        imdb_id = _catalog_id(target.item.get("imdb_id"))
        tmdb_id = _catalog_id(target.item.get("tmdb_id"))
        if imdb_id is not None:
            params["imdb_id"] = imdb_id
        elif tmdb_id is not None:
            params["tmdb_id"] = tmdb_id
        elif include_fallback_query:
            params["query"] = target.title.lower()
        return params

    parent_imdb_id = _catalog_id(target.item.get("imdb_id"))
    parent_tmdb_id = _catalog_id(target.item.get("tmdb_id"))
    episode_imdb_id = _catalog_id(target.subtitle_holder.get("imdb_id"))
    episode_tmdb_id = _catalog_id(target.subtitle_holder.get("tmdb_id"))

    if episode_imdb_id is not None:
        params["imdb_id"] = episode_imdb_id
    elif episode_tmdb_id is not None:
        params["tmdb_id"] = episode_tmdb_id
    elif parent_imdb_id is not None:
        params["parent_imdb_id"] = parent_imdb_id
        params["season_number"] = target.season_number
        params["episode_number"] = target.episode_number
    elif parent_tmdb_id is not None:
        params["parent_tmdb_id"] = parent_tmdb_id
        params["season_number"] = target.season_number
        params["episode_number"] = target.episode_number
    elif include_fallback_query:
        params["query"] = target_label(target).lower()

    return {key: value for key, value in params.items() if value is not None}


def rank_subtitles(results: list[dict[str, Any]], target: CatalogTarget) -> list[SubtitleCandidate]:
    """Convert OpenSubtitles results into ranked downloadable candidates."""
    candidates: list[SubtitleCandidate] = []
    for result in results:
        attrs = result.get("attributes", {})
        files = attrs.get("files") or []
        if not files:
            continue

        first_file = files[0]
        file_id = _optional_int(first_file.get("file_id"))
        if file_id is None:
            continue

        score = _score_result(attrs, first_file, target)
        candidates.append(
            SubtitleCandidate(
                result_id=str(result.get("id") or attrs.get("subtitle_id") or ""),
                file_id=file_id,
                language=str(attrs.get("language") or ""),
                score=score,
                release=str(attrs.get("release") or first_file.get("file_name") or ""),
                download_count=_optional_int(attrs.get("download_count")) or 0,
                new_download_count=_optional_int(attrs.get("new_download_count")) or 0,
                ratings=float(attrs.get("ratings") or 0),
                from_trusted=bool(attrs.get("from_trusted")),
                moviehash_match=bool(attrs.get("moviehash_match")),
            )
        )

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def apply_candidate(target: CatalogTarget, candidate: SubtitleCandidate) -> None:
    """Write selected candidate metadata to the catalog target."""
    target.subtitle_holder["subtitle_id"] = candidate.file_id
    target.subtitle_holder["subtitle_source_language"] = candidate.language
    target.subtitle_holder["subtitle_result_id"] = candidate.result_id
    target.subtitle_holder["subtitle_release"] = candidate.release
    target.subtitle_holder["translation_needed"] = candidate.language != "pl"


def _score_result(
    attrs: dict[str, Any], first_file: dict[str, Any], target: CatalogTarget
) -> int:
    score = 0
    if bool(attrs.get("moviehash_match")):
        score += 100
    if bool(attrs.get("from_trusted")):
        score += 25
    if bool(attrs.get("hd")):
        score += 10
    if bool(attrs.get("hearing_impaired")):
        score -= 50
    if bool(attrs.get("foreign_parts_only")):
        score -= 80
    if bool(attrs.get("machine_translated")) or bool(attrs.get("ai_translated")):
        score -= 80

    score += min(_optional_int(attrs.get("download_count")) or 0, 5000) // 200
    score += min(_optional_int(attrs.get("new_download_count")) or 0, 1000) // 100
    score += int(float(attrs.get("ratings") or 0) * 2)

    feature_details = attrs.get("feature_details") or {}
    if target.media_type == "episode":
        if _optional_int(feature_details.get("season_number")) == target.season_number:
            score += 20
        if _optional_int(feature_details.get("episode_number")) == target.episode_number:
            score += 20
    elif _optional_int(feature_details.get("year")) == _optional_int(target.item.get("year")):
        score += 15

    file_name = str(first_file.get("file_name") or attrs.get("release") or "").lower()
    for token in _release_tokens(target):
        if token and token in file_name:
            score += 8

    return score


def _release_tokens(target: CatalogTarget) -> list[str]:
    magnet = str(target.item.get("magnet") or "").lower()
    useful_tokens = []
    for token in ("yts", "yify", "rarbg", "qxr", "bluray", "webrip", "web-dl", "x265", "x264"):
        if token in magnet:
            useful_tokens.append(token)
    return useful_tokens


def _catalog_id(value: Any) -> int | None:
    if isinstance(value, str) and value.lower().startswith("tt"):
        value = value[2:]
    return _optional_int(value)


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
