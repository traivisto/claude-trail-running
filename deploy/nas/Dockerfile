# Runtime image for the headless coach on a Synology NAS (x86_64).
# Contains: Node (for Claude Code CLI and npx-based MCP servers), Python 3 + uv (for uvx-based MCP
# servers such as garmin_mcp), git. No personal data and no credentials are baked in; everything
# personal is mounted at runtime (see compose.yaml).
FROM node:22-bookworm-slim

# Versions are pinned so an upgrade is a deliberate act: change the numbers (here, the uv tag below, and
# the garmin_mcp commit / oura-mcp version in mcp.json), rebuild with --no-cache and run the tests in
# deploy/nas/README.md ("Upgrading").
ARG CLAUDE_CODE_VERSION=2.1.328

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 git openssh-client curl ca-certificates tzdata procps jq \
 && rm -rf /var/lib/apt/lists/*

# uv / uvx (Python tool runner used by the Garmin MCP server). Pin the tag after the first build.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /usr/local/bin/

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && npm cache clean --force

ENV TZ=Europe/Helsinki \
    HOME=/home/coach \
    PYTHONIOENCODING=utf-8 \
    DISABLE_AUTOUPDATER=1

# The container runs as an unprivileged uid:gid chosen in compose.yaml (the NAS "coach" user).
# HOME is a mounted volume, so tokens and Claude settings persist across runs.
RUN mkdir -p /home/coach /workspace && chmod 777 /home/coach
# OpenSSH refuses to run for a uid without a passwd entry; give the NAS "coach" uid/gid (1031:100) a name.
RUN useradd -u 1031 -g 100 -d /home/coach -M -s /bin/bash coach
WORKDIR /workspace

CMD ["bash"]
