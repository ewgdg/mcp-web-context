from fastapi import APIRouter
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from ..search import GoogleSearch, SearchResultEntry

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query to find relevant web pages")
    max_results: int = Field(
        default=10, description="Maximum number of search results to return"
    )


class SearchResult(BaseModel):
    results: list[SearchResultEntry] = Field(
        ..., description="List of search results with URLs and snippets"
    )


@router.post(
    "",
    summary="Web search engine",
)
async def search_web_pages(request: SearchRequest) -> SearchResult:
    """
    Search the web using Google Custom Search API to find relevant pages.

    Returns search results with URLs, titles, and snippets that can be used
    with the fetch_web_content tool to get full page content.
    """
    search_engine = GoogleSearch(request.query)
    res = await search_engine.search(max_results=request.max_results)
    return SearchResult(results=res if res is not None else [])


def register_mcp_tools(mcp: FastMCP):
    """Register MCP tools for this router"""
    mcp.tool()(search_web_pages)
