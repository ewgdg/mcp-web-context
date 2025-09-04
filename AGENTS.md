# Repository Guidelines

## Project Structure & Module Organization
- Source: `src/mcp_web_context/` (FastAPI app and MCP server).
- Key modules: `main.py` (app entry), `routers/` (API routes), `agents/` (agent logic), `scraper.py` (Patchright browser), `search.py` (Google CSE), `cache.py` (async cache), `config.py` (AI providers/models).
- Tests: `tests/` (unit/integration); Logs/Screenshots: `logs/`.

## Build, Test, and Development Commands
- Install deps: `uv sync`
- Run API: `uv run -- uvicorn 'src.mcp_web_context.main:app' --host=0.0.0.0 --port=8000`
- API docs: open `http://localhost:8000/docs`
- Run tests: `uv run pytest -q`
- Lint/format (dev deps): `uv run ruff check .` and `uv run ruff format .`
- Docker: `docker compose up --build` (API at `http://localhost:8000`; KasmVNC at `https://localhost:6901`).

## Coding Style & Naming Conventions
- Python 3.13; 4‑space indentation; use type hints.
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep functions small; prefer explicit returns and dataclasses/Pydantic models for DTOs.
- Follow Ruff defaults; fix warnings before submitting.

## Testing Guidelines
- Framework: `pytest` (+ `pytest-asyncio`).
- Location/pattern: files in `tests/` named `test_*.py`; use `async` tests where appropriate.
- Scope: cover routers (status codes, payloads), agents (happy/edge paths), and scraper/search with mocks.
- Run: `uv run pytest -q`; add fixtures for network/browser isolation.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise scope, reference issues (e.g., "fix: handle 429 in scraper (#123)").
- PRs: include summary, rationale, test coverage notes, and run outputs or screenshots where relevant (e.g., API responses, failing → passing).
- Checks: ensure `pytest` passes; run `ruff check` and `ruff format`.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` or container env vars: required `GOOGLE_API_KEY`, `GOOGLE_CX_KEY`; optional `DATABASE_URL`.
- Model/provider settings live in `config.yaml` (ordered primary → fallback). Validate credentials before enabling agents.
- Rate limits and caching are built‑in—avoid duplicate fetches; inspect `logs/` for failures/screenshots.
