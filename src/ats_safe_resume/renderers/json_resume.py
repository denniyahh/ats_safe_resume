"""JSON Resume renderer."""

import json
from pathlib import Path

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer


class JsonResumeRenderer(BaseRenderer):
    """Export resume to JSON Resume schema."""

    def render(self, resume: Resume, output_path: Path) -> None:
        data = resume.to_json_resume()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
