"""Base renderer interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from ats_safe_resume.models import Resume


class BaseRenderer(ABC):
    """All renderers implement this interface."""

    @abstractmethod
    def render(self, resume: Resume, output_path: Path) -> None:
        """Render resume to output_path."""
