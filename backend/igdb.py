"""Compatibility import for the importer-only IGDB client.

Runtime game search must use the local database through ``games.service``.
"""

from integrations.igdb.client import IGDBClient, IGDBClientError

__all__ = ["IGDBClient", "IGDBClientError"]
