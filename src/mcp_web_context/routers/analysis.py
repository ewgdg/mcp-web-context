from fastapi import APIRouter
from mcp.server.fastmcp import FastMCP

from ..agents.web_content_analyzer import (
    WebContentAnalyzer,
    ExtractedContent,
    AnalyzeRequest,
)

router = APIRouter(prefix="/smart-analyze", tags=["analysis"])


@router.post(
    "",
    summary="AI-powered content extraction and analysis",
    response_model=ExtractedContent,
)
async def smart_analyze_content(request: AnalyzeRequest) -> ExtractedContent:
    """
    Extract relevant content from a URL using AI analysis.

    Uses llm model to analyze web content, extract only information
    relevant to the query, and assess content reliability with trust scores.
    """
    analyzer = WebContentAnalyzer()
    result = await analyzer.analyze_url(request)
    return result


def register_mcp_tools(mcp: FastMCP):
    """Register MCP tools for this router"""
    mcp.tool()(smart_analyze_content)
