"""Wspólny interfejs źródeł: fetch() -> list[Announcement] (sekcja 8.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..model import Announcement


class BaseSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[Announcement]: ...
