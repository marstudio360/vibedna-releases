FROM python:3.12-slim

# System deps for faster-whisper (av/ctranslate2 prebuilt wheels handle most cases,
# but ffmpeg fallback helps for caption-less videos)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Jester writes runtime data here (cache, index, logs)
RUN mkdir -p /data && chmod 777 /data
ENV JESTER_HOME=/data

# For local installs: buyers run `python server.py` directly (stdio MCP).
# For Cloud Run / mcpize hosting: server.py serves the canonical MCP HTTP
# transport (streamable-http at /mcp) when JESTER_TRANSPORT=http. PORT comes
# from Cloud Run automatically (8080).
ENV JESTER_TRANSPORT=http
CMD ["python", "server.py"]
