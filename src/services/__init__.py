"""Services module for Hackflix background workers.

Services are imported lazily to avoid requiring libtorrent
at module import time (useful for testing).
"""


def __getattr__(name: str):
    """Lazy import services."""
    if name == "MetadataService":
        from src.services.metadata_service import MetadataService

        return MetadataService
    if name == "TorrentService":
        from src.services.torrent_service import TorrentService

        return TorrentService
    if name == "DownloadType":
        from src.services.torrent_service import DownloadType

        return DownloadType
    if name == "DownloadContext":
        from src.services.torrent_service import DownloadContext

        return DownloadContext
    if name == "PlayerService":
        from src.services.player_service import PlayerService

        return PlayerService
    if name == "PipelineService":
        from src.services.pipeline_service import PipelineService

        return PipelineService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MetadataService",
    "TorrentService",
    "DownloadType",
    "DownloadContext",
    "PlayerService",
    "PipelineService",
]
