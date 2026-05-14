"""Tests for catalog subtitle matching helpers."""

from src.utils.subtitle_catalog_matcher import (
    CatalogTarget,
    apply_candidate,
    build_search_params,
    iter_catalog_targets,
    rank_subtitles,
)


def test_iter_catalog_targets_returns_movies_and_episodes() -> None:
    """Catalog traversal includes movies and series episodes."""
    catalog = {
        "items": [
            {"type": "movie", "title": "Movie", "subtitle_id": None},
            {
                "type": "series",
                "title": "Show",
                "seasons": [
                    {
                        "season_number": 1,
                        "episodes": [{"number": 2, "title": "Episode"}],
                    }
                ],
            },
        ]
    }

    targets = iter_catalog_targets(catalog)

    assert len(targets) == 2
    assert targets[0].media_type == "movie"
    assert targets[1].media_type == "episode"
    assert targets[1].season_number == 1
    assert targets[1].episode_number == 2


def test_build_movie_search_params_prefers_imdb_id() -> None:
    """Movie search uses IMDb ID before text query."""
    item = {"title": "Ghost", "imdb_id": "tt0094625", "tmdb_id": 9323}
    target = CatalogTarget(item=item, subtitle_holder=item, media_type="movie", title="Ghost")

    params = build_search_params(target, "pl")

    assert params["imdb_id"] == 94625
    assert params["languages"] == "pl"
    assert params["type"] == "movie"
    assert "query" not in params


def test_build_episode_search_params_uses_parent_id_with_numbers() -> None:
    """Episode search uses parent show ID with season and episode."""
    item = {"title": "The Wire", "imdb_id": "0306414"}
    episode = {"number": 2, "title": "The Detail"}
    target = CatalogTarget(
        item=item,
        subtitle_holder=episode,
        media_type="episode",
        title="The Wire",
        season_number=1,
        episode_number=2,
        episode_title="The Detail",
    )

    params = build_search_params(target, "en")

    assert params["parent_imdb_id"] == 306414
    assert params["season_number"] == 1
    assert params["episode_number"] == 2
    assert "imdb_id" not in params


def test_build_episode_search_params_prefers_episode_id() -> None:
    """Episode-specific ID is sent without parent season parameters."""
    item = {"title": "The Wire", "imdb_id": "0306414"}
    episode = {"number": 2, "title": "The Detail", "imdb_id": "tt0749436"}
    target = CatalogTarget(
        item=item,
        subtitle_holder=episode,
        media_type="episode",
        title="The Wire",
        season_number=1,
        episode_number=2,
    )

    params = build_search_params(target, "en")

    assert params["imdb_id"] == 749436
    assert "parent_imdb_id" not in params
    assert "season_number" not in params


def test_rank_subtitles_scores_and_skips_results_without_file_id() -> None:
    """Ranking returns downloadable candidates ordered by score."""
    item = {"title": "Movie", "year": 1995, "magnet": "magnet:?dn=Movie.1995.BluRay.QxR"}
    target = CatalogTarget(item=item, subtitle_holder=item, media_type="movie", title="Movie")
    results = [
        {"id": "missing", "attributes": {"files": []}},
        {
            "id": "1",
            "attributes": {
                "language": "pl",
                "download_count": 10,
                "from_trusted": False,
                "files": [{"file_id": 101, "file_name": "Movie.1995.WEBRip.srt"}],
            },
        },
        {
            "id": "2",
            "attributes": {
                "language": "pl",
                "download_count": 2000,
                "ratings": 5,
                "from_trusted": True,
                "hd": True,
                "moviehash_match": True,
                "feature_details": {"year": 1995},
                "files": [{"file_id": 202, "file_name": "Movie.1995.BluRay.QxR.srt"}],
            },
        },
    ]

    candidates = rank_subtitles(results, target)

    assert [candidate.file_id for candidate in candidates] == [202, 101]
    assert candidates[0].score > candidates[1].score


def test_apply_candidate_updates_catalog_holder() -> None:
    """Selected candidate is written to compatible catalog fields."""
    item = {"title": "Movie"}
    target = CatalogTarget(item=item, subtitle_holder=item, media_type="movie", title="Movie")
    candidate = rank_subtitles(
        [
            {
                "id": "99",
                "attributes": {
                    "language": "en",
                    "release": "Movie.1995",
                    "files": [{"file_id": 123, "file_name": "Movie.1995.srt"}],
                },
            }
        ],
        target,
    )[0]

    apply_candidate(target, candidate)

    assert item["subtitle_id"] == 123
    assert item["subtitle_source_language"] == "en"
    assert item["subtitle_result_id"] == "99"
    assert item["translation_needed"] is True
