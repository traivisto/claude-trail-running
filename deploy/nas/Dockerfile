# Runtime image for the headless coach on a Synology NAS (x86_64).
# Contains: Node (for Claude Code CLI and npx-based MCP servers), Python 3 + uv (for uvx-based MCP
# servers such as garmin_mcp), git. No personal data and no credentials are baked in; everything
# personal is mounted at runtime (see compose.yaml).
FROM node:22-bookworm-slim

# Pin after the first successful build (e.g. 2.1.x) so an upgrade is a deliberate act.
ARG CLAUDE_CODE_VERSION=latest

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 git openssh-client curl ca-certificates tzdata procps jq \
 && rm -rf /var/lib/apt/lists/*

# uv / uvx (Python tool runner used by the Garmin MCP server). Pin the tag after the first build.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && npm cache clean --force

ENV TZ=Europe/Helsinki \
    HOME=/home/coach \
    PYTHONIOENCODING=utf-8 \
    DISABLE_AUTOUPDATER=1

# The container runs as an unprivileged uid:gid chosen in compose.yaml (the NAS "coach" user).
# HOME is a mounted volume, so tokens and Claude settings persist across runs.
RUN mkdir -p /home/coach /workspace && chmod 777 /home/coach
WORKDIR /workspace

CMD ["bash"]
