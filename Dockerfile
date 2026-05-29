# ATS Safe Resume — Docker Image
#
# Python 3 + Typst for deterministic PDF generation.
# All 5 output formats from a single markdown source.
#
# Build:
#   docker build -t ats_safe_resume .
#
# Run:
#   docker run --rm -v $(pwd):/data ats_safe_resume /data/resume.md

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/denniyahh/ats_safe_resume"
LABEL org.opencontainers.image.description="ATS Safe Resume builder"
LABEL org.opencontainers.image.licenses="MIT"

# Install system fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates fontconfig unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Source Sans 3 and Source Code Pro fonts
RUN mkdir -p /usr/local/share/fonts \
    && curl -fsSL "https://github.com/adobe-fonts/source-sans/releases/download/3.052R/TTF-source-sans-3.052R.zip" -o /tmp/sourcesans.zip \
    && unzip -qo /tmp/sourcesans.zip -d /usr/local/share/fonts/ \
    && curl -fsSL "https://github.com/adobe-fonts/source-code-pro/releases/download/2.042R-u%2F1.062R-i%2F1.026R-vf/TTF-source-code-pro-2.042R-u_1.062R-i.zip" -o /tmp/sourcecode.zip \
    && unzip -qo /tmp/sourcecode.zip -d /usr/local/share/fonts/ \
    && fc-cache -f /usr/local/share/fonts/

# Install Python dependencies
COPY pyproject.toml /app/
COPY src/ /app/src/
WORKDIR /app
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["ats-safe-resume"]
CMD ["/data/resume.md"]
