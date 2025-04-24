"""
Base repository classes for the inventory app.

This module re-exports the base repository classes from core.repositories
for use in the inventory app.
"""

from core.repositories import BaseRepository, RepositoryError

# Re-export the classes
__all__ = ['BaseRepository', 'RepositoryError']