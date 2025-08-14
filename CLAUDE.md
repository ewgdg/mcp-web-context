# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server for web browsing and search built with FastAPI that provides two main capabilities:

- Web page content extraction using headless browser automation (Camoufox)
- Google Custom Search API integration

The service runs in a Docker container with Wayland-based VNC for browser visualization and debugging.

## Development Commands

### Dependencies and Environment

- Uses `uv` for Python package management
- Python 3.13+ required
- Install dependencies: `uv sync`
- Run the service locally: `uv run -- uvicorn 'src.mcp_web_context.main:app' --host=0.0.0.0 --port=8000`

### Code Quality and Testing

- Run browser test: `uv run test/test_browser.py`
- Test API endpoints: Visit `http://localhost:8000/docs` for interactive OpenAPI documentation
- **Note**: Some scripts reference `app` directory but code is in `src/mcp_web_context/` - this needs to be fixed

### Docker Development

- Build and run: `docker compose up --build`
- Service runs on port 8000, VNC on port 5910
- VNC credentials: wayvnc/wayvnc for debugging browser sessions
- Logs and screenshots saved to `./logs/` directory

## Architecture

### Core Components

**FastAPI Service (`main.py`)**:

- `/health` - Health check endpoint
- `/scrape` - POST endpoint for scraping multiple URLs
- `/search` - POST endpoint for Google Custom Search
- `/mcp/sse` and `/mcp/messages` - MCP (Model Context Protocol) endpoints

**Browser Management (`scraper.py`)**:

- `CamoufoxScraper` class manages Camoufox browser instances
- Load balancing across max 3 browser instances (5 tabs/browser threshold)
- Per-domain rate limiting with random delays
- Automatic screenshot capture on scraping failures for debugging

**Search Integration (`search.py`)**:

- `GoogleSearch` class for Google Custom Search API
- Requires `GOOGLE_API_KEY` and `GOOGLE_CX_KEY` environment variables
- Filters out YouTube results and handles pagination

**Caching System (`cache.py`)**:

- SQLite-based async caching with 3-day expiration
- Caches scraping results when content length > 250 characters
- Background cleanup job runs daily
- Cache decorator supports conditional caching via `allow_cache` parameter

### Key Features

- **Browser Pool Management**: Automatic load balancing across multiple browser instances
- **Rate Limiting**: Per-domain semaphores prevent overwhelming sites
- **Error Recovery**: Screenshot capture and detailed logging for failed scrapes
- **Content Processing**: BeautifulSoup-based HTML cleaning and text extraction with image relevance scoring
- **Container Ready**: Full Docker setup with GPU acceleration support for browser rendering

### Environment Variables

Required (create `.env` file):

- `GOOGLE_API_KEY` - Required for search functionality  
- `GOOGLE_CX_KEY` - Required for Google Custom Search Engine
- `OPENAI_API_KEY` - Required for AI-powered content analysis agent

Optional:

- `RENDER_GROUP_GID` - For GPU device access in container
- `DATABASE_URL` - Defaults to SQLite in container cache directory

### Browser Configuration

The service uses Camoufox (Firefox-based) with special configuration for containerized environments:

- Wayland support for VNC rendering
- Anti-fingerprinting and stealth features built-in
- Automatic user agent and fingerprint spoofing
- Firefox ESR as the base browser engine

## Testing and Debugging

Access the VNC viewer at `http://localhost:5910` to visually debug browser sessions. Screenshots of failed scrapes are automatically saved to `logs/screenshots/`.

The service includes a browser detection test that visits browserscan.net to verify the browser appears "normal" to anti-bot systems.

## MCP Integration

This service implements the Model Context Protocol (MCP) and can be used as an MCP server:

- Provides `/mcp/sse` and `/mcp/messages` endpoints via FastMCP
- Exposes MCP tools: `fetch_web_content`, `search_web_pages`, `smart_analyze_content`
- MCP server name: "web-browsing-mcp"
- Can be connected to by MCP clients for programmatic access

## Project Structure

The codebase follows a modular FastAPI structure:

- `src/mcp_web_context/main.py` - FastAPI app with MCP integration via FastMCP
- `src/mcp_web_context/routers/` - API route handlers (scraping, search, analysis)
- `src/mcp_web_context/scraper.py` - Browser pool management with Camoufox
- `src/mcp_web_context/search.py` - Google Custom Search integration
- `src/mcp_web_context/cache.py` - SQLite caching with async support
- `src/mcp_web_context/agents/` - AI-powered content analysis agents
