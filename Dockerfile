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

# Install system packages
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
    # Python (ATS normalization, JSON generation)
    python3 \
    # Font download tools
    curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Source Sans 3 and Source Code Pro fonts from GitHub releases
RUN mkdir -p /usr/local/share/fonts \
    && curl -fsSL "https://github.com/adobe-fonts/source-sans/releases/download/3.052R/TTF-source-sans-3.052R.zip" -o /tmp/sourcesans.zip \
    && unzip -qo /tmp/sourcesans.zip -d /usr/local/share/fonts/ \
    && curl -fsSL "https://github.com/adobe-fonts/source-code-pro/releases/download/2.042R-u%2F1.062R-i%2F1.026R-vf/TTF-source-code-pro-2.042R-u_1.062R-i.zip" -o /tmp/sourcecode.zip \
    && unzip -qo /tmp/sourcecode.zip -d /usr/local/share/fonts/ \
    && fc-cache -f /usr/local/share/fonts/

# Copy build system
WORKDIR /app
COPY templates/        /app/templates/
COPY themes/           /app/themes/
COPY resume-preamble.tex /app/
COPY build_resume.sh   /app/
COPY reference.docx    /app/

RUN chmod +x /app/build_resume.sh

ENTRYPOINT ["/app/build_resume.sh"]
