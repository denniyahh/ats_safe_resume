"""HTML renderer using Jinja2."""

from pathlib import Path

from jinja2 import Environment, PackageLoader

from ats_safe_resume.models import Resume
from ats_safe_resume.renderers.base import BaseRenderer
from ats_safe_resume import inline_md


class HtmlRenderer(BaseRenderer):
    """Render resume to HTML using Jinja2 template."""

    def render(self, resume: Resume, output_path: Path) -> None:
        env = Environment(
            loader=PackageLoader("ats_safe_resume", "templates"),
            autoescape=True,
        )
        env.filters['inline_markdown'] = inline_md.to_html

        template = env.get_template("resume.html")
        html = template.render(resume=resume)
        output_path.write_text(html)
