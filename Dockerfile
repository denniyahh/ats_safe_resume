# ATS Safe Resume — Docker Image
#
# Pinned versions of Pandoc + TeX Live + fonts for reproducible builds.
# No LaTeX install required on the host machine.
#
# Build:
#   docker build -t ats_safe_resume .
#
# Run:
#   docker run --rm -v $(pwd):/data ats_safe_resume /data/resume.md

FROM ubuntu:24.04

LABEL org.opencontainers.image.source="https://github.com/denniyahh/ats_safe_resume"
LABEL org.opencontainers.image.description="ATS Safe Resume builder"
LABEL org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive

# Install TeX Live (minimal set for resume builds), Pandoc, fonts, Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Pandoc (from Ubuntu repos — stable, no need for bleeding edge)
    pandoc \
    # TeX Live: base + LuaLaTeX + KOMA-script + fontspec + enumitem
    texlive-latex-base \
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-luatex \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    lmodern \
    # Fonts: Source Sans 3, Source Code Pro
    fonts-source-sans-pro \
    fonts-source-code-pro \
    # Python (ATS normalization, JSON generation)
    python3 \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy build system
WORKDIR /app
COPY templates/        /app/templates/
COPY themes/           /app/themes/
COPY resume-preamble.tex /app/
COPY build_resume.sh   /app/
COPY reference.docx    /app/ 2>/dev/null || true

RUN chmod +x /app/build_resume.sh

ENTRYPOINT ["/app/build_resume.sh"]
