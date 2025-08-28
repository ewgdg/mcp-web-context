# MCP Web Context

A Model Context Protocol (MCP) server for web browsing, content extraction, and search built with FastAPI.

## Features

- **Web Content Extraction**: Headless browser automation using Patchright
- **Google Custom Search**: Integration with Google Custom Search API  
- **AI-Powered Analysis**: Multi-provider AI content analysis (OpenAI, OpenAI-compatible, Anthropic, etc.)
- **Intelligent Caching**: SQLite-based caching with automatic cleanup
- **Docker Ready**: Full containerized setup with VNC debugging

## Quick Start

### Using Docker (Recommended)

```bash
git clone <repository-url>
cd mcp-web-context
cp .env.example .env  # Edit with your API keys
docker compose up --build
```


- API: <http://localhost:8000>
- VNC Debug: <http://localhost:5910> (wayvnc/wayvnc) - Use a VNC client (e.g., TigerVNC)

### Local Development

```bash
uv sync
cp .env.example .env  # Edit with your API keys
uv run -- uvicorn 'src.mcp_web_context.main:app' --host=0.0.0.0 --port=8000
```

## Configuration

Copy `.env.example` to `.env` and configure your API keys. See `config.yaml` for AI provider configuration (supports OpenAI, OpenAI-compatible, Anthropic, Ollama, etc.).

## API Endpoints

- `GET /health` - Health check
- `GET /docs` - OpenAPI documentation
- `GET /logs` - Web-based log file browser with delete functionality
- `/mcp/sse` - MCP server endpoints (provided by FastMCP)

## MCP Tools

- `fetch_web_content`: Extract content from web pages
- `search_web_pages`: Search using Google Custom Search
- `smart_analyze_content`: Fetch and analyze web content with AI

## Requirements

- Python 3.13+
- Docker (recommended)
- Google Custom Search API credentials
- AI provider API key (OpenAI, Anthropic, etc.)
- Firefox ESR (handled automatically in Docker)
