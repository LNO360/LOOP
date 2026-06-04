# Hermes Agent — NousResearch autonomous agent
# Hermes requires Python 3.11 (not 3.12)
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV HERMES_HOME=/root/.hermes
ENV PATH="/root/.local/bin:/opt/hermes/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ripgrep ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Node.js (LTS) — required by the `browser` toolset's agent-browser CLI.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer used by Hermes)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone Hermes from official source
RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /opt/hermes

WORKDIR /opt/hermes

# Create venv with Python 3.11 and install Hermes
# Try full [all] extras first, fall back to core if some extras fail
RUN uv venv .venv --python 3.11 && \
    uv pip install --python .venv/bin/python -e ".[all]" 2>/dev/null || \
    uv pip install --python .venv/bin/python -e "."

# Regulatory PDF → markdown (TRAI, DoT, TDSAT research via terminal tool).
# Install into BOTH the venv and the system python — Hermes' terminal tool may
# invoke either depending on shell context (login shell resolves to system).
RUN uv pip install --python .venv/bin/python markitdown pymupdf
RUN pip install --no-cache-dir markitdown pymupdf

# ── Browser toolset (local headless Chromium via agent-browser) ──────────
# Hermes' built-in `browser` toolset (enabled in config.yaml) drives a local
# headless Chromium through the agent-browser CLI (Node).
#
# We install Debian's Chromium via apt (pulls in all required system libs) and
# point agent-browser at it with AGENT_BROWSER_EXECUTABLE_PATH — the same env
# var Hermes' own install.sh sets. This makes agent-browser use the system
# browser and SKIP its "Chrome for Testing" download, which has no linux-arm64
# build and is a flaky ~150MB external fetch from googleapis.
RUN apt-get update && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g agent-browser
ENV AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium

# Create the ~/.hermes data directory structure
RUN mkdir -p \
    /root/.hermes/skills \
    /root/.hermes/sessions \
    /root/.hermes/cron \
    /root/.hermes/logs \
    /root/.hermes/memories

# Copy config and startup script
COPY config.yaml /root/.hermes/config.yaml
COPY profile-cron-config.yaml /opt/lno-hermes/profile-cron-config.yaml
COPY SOUL.md /root/.hermes/SOUL.md
COPY entrypoint.sh /entrypoint.sh
COPY scripts/ensure_cron_profile.sh /opt/lno-hermes/scripts/ensure_cron_profile.sh
RUN chmod +x /entrypoint.sh

# Skill files are mounted at runtime via docker-compose volume
# (so they can be edited without rebuilding the image)

ENTRYPOINT ["/entrypoint.sh"]
