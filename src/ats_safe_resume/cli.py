"""CLI entry point."""

import argparse
import json
from pathlib import Path

from ats_safe_resume.parser import parse
from ats_safe_resume.models import Resume
from ats_safe_resume.renderers import PdfRenderer
from ats_safe_resume.renderers.docx import DocxRenderer
from ats_safe_resume.renderers.html import HtmlRenderer
from ats_safe_resume.renderers.txt import TxtRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer


def build():
    parser = argparse.ArgumentParser(description="Build resume from markdown")
    parser.add_argument("input", help="Input resume.md or resume.json")
    parser.add_argument("--formats", default="pdf,docx,html,txt,json",
                        help="Comma-separated output formats")
    parser.add_argument("--out-dir", default="dist-v2",
                        help="Output directory (default: dist-v2)")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation after build")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse input
    text = input_path.read_text()
    if input_path.suffix == ".json":
        resume = Resume.model_validate(json.loads(text))
    else:
        resume = parse(text)

    # Save canonical JSON
    json_path = output_dir / "resume.json"
    JsonResumeRenderer().render(resume, json_path)
    print(f"  ✅ {json_path}")

    # Render requested formats
    renderers = {
        "pdf": PdfRenderer,
        "docx": DocxRenderer,
        "html": HtmlRenderer,
        "txt": TxtRenderer,
        "json": JsonResumeRenderer,
    }

    for fmt in args.formats.split(","):
        fmt = fmt.strip()
        if fmt == "json":
            continue  # already rendered as canonical
        ext = fmt
        output_path = output_dir / f"resume.{ext}"
        try:
            renderers[fmt]().render(resume, output_path)
            print(f"  ✅ {output_path}")
        except Exception as e:
            print(f"  ❌ {fmt}: {e}")
            if args.validate:
                raise

    print(f"\nDone — output in {output_dir}/")


if __name__ == "__main__":
    build()
