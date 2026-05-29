"""Renderers package."""

from ats_safe_resume.renderers.base import BaseRenderer
from ats_safe_resume.renderers.pdf import PdfRenderer as TypstPdfRenderer
from ats_safe_resume.renderers.pandoc_pdf import PandocPdfRenderer
from ats_safe_resume.renderers.docx import DocxRenderer
from ats_safe_resume.renderers.html import HtmlRenderer
from ats_safe_resume.renderers.txt import TxtRenderer
from ats_safe_resume.renderers.json_resume import JsonResumeRenderer

# Default PDF renderer (Pandoc/LuaLaTeX — matches v1 Eisvogel quality)
PdfRenderer = PandocPdfRenderer
# Fallback if Pandoc/TeX Live unavailable (Typst — smaller install size)
TypstFallback = TypstPdfRenderer

__all__ = [
    "BaseRenderer",
    "PdfRenderer",
    "TypstFallback",
    "PandocPdfRenderer",
    "DocxRenderer",
    "HtmlRenderer",
    "TxtRenderer",
    "JsonResumeRenderer",
]
