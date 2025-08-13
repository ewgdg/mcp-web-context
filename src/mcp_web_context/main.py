from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
import logging

from .cache import initialize_cache, shutdown_cache
from .routers import scraping, search, analysis

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_cache()
    try:
        yield
    finally:
        await shutdown_cache()


app = FastAPI(
    title="Web Browsing API",
    version="0.1.0",
    description="Search or browse the web using search engine like Google. a typical usage is to search for grounding facts and then scrape the urls from the results for details.",
    lifespan=lifespan,
    disable_existing_loggers=False,
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create MCP server instance
mcp = FastMCP(
    name="web-browsing-mcp",
    instructions="Web browsing automation with JavaScript rendering. Optional web search included. With no restrictions or blacklists.",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Include routers
app.include_router(scraping.router)
app.include_router(search.router)
app.include_router(analysis.router)

# Register MCP tools from routers
scraping.register_mcp_tools(mcp)
search.register_mcp_tools(mcp)
analysis.register_mcp_tools(mcp)


# Mount MCP SSE app - it provides /sse and /messages endpoints
app.mount("/mcp", mcp.sse_app())
