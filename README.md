# MCP Web Search

A Model Context Protocol (MCP) server for web browsing, content extraction, and search built with FastAPI.

## Features

- **Web Content Extraction**: Headless browser automation using Zendriver
- **Google Custom Search**: Integration with Google Custom Search API  
- **AI-Powered Analysis**: OpenAI-powered content analysis
- **Intelligent Caching**: SQLite-based caching with automatic cleanup
- **Docker Ready**: Full containerized setup with VNC debugging

## Quick Start

### Using Docker (Recommended)

```bash
git clone <repository-url>
cd mcp-web-search
cp .env.example .env  # Edit with your API keys
docker compose up --build
```

**Note**: GPU passthrough is required for wayvnc to start. Currently configured for NVIDIA GPUs.

- API: <http://localhost:8000>
- VNC Debug: <http://localhost:5910> (wayvnc/wayvnc) - Use a VNC client (e.g., RealVNC)

#### Chrome Version Management

The Docker container uses a pinned Chrome version for reproducible browser behavior. To update to the latest stable Chrome version:

```bash
./update-chrome-version.sh  # Updates chrome-version.txt
docker compose build        # Rebuild with new Chrome version
```

### Local Development

```bash
uv sync
cp .env.example .env  # Edit with your API keys
uv run -- uvicorn 'src.scraper.main:app' --host=0.0.0.0 --port=8000
```

## Configuration

Copy `.env.example` to `.env` and add your Google Search API key, Custom Search Engine key, and OpenAI API key.

## API Endpoints

- `GET /health` - Health check
- `GET /docs` - OpenAPI documentation
- `/mcp/sse` - MCP server endpoints (provided by FastMCP)

## MCP Tools

- `fetch_web_content`: Extract content from web pages
- `search_web_pages`: Search using Google Custom Search
- `smart_analyze_content`: Fetch and analyze web content with AI

## Requirements

- Python 3.13+
- Docker (recommended)
- NVIDIA GPU (for Docker VNC)
- Google Custom Search API credentials
- OpenAI API key
