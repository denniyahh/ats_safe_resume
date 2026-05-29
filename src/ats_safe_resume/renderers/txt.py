"""TXT renderer using Jinja2."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer
from ats_safe_resume import ats_normalize
from ats_safe_resume import inline_md


class TxtRenderer(BaseRenderer):
    """Render resume to plain text using Jinja2 template."""

    def render(self, resume: Resume, output_path: Path) -> None:
        env = Environment(
            loader=PackageLoader("ats_safe_resume", "templates"),
            autoescape=False,
        )
        env.filters['strip_markdown'] = inline_md.strip_markdown
        env.filters['ats_normalize'] = ats_normalize.normalize

        template = env.get_template("resume.txt")
        text = template.render(resume=resume)
        output_path.write_text(text)
