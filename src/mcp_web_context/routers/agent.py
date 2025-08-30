"""
Agent Router Module

Centralizes all agent-related endpoints under the /agent prefix.
"""

from fastapi import APIRouter
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..agents.intelligent_search_agent import (
    IntelligentSearchAgent,
    FinalAnswer,
)
from ..agents.web_content_analyzer import (
    WebContentAnalyzer,
    ExtractedContent,
    AnalyzeRequest,
)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentSearchRequest(BaseModel):
    """Request model for intelligent search agent."""

    query: str = Field(
        ..., description="The search query to find comprehensive answer for"
    )
    max_iterations: int = Field(
        default=20,
        description="Maximum iterations for search-analyze loop",
        ge=1,
        le=100,
    )


@router.post(
    "/search",
    summary="Intelligent iterative search for comprehensive answers",
    response_model=FinalAnswer,
)
async def intelligent_search(request: AgentSearchRequest) -> FinalAnswer:
    """
    Perform intelligent iterative search to find comprehensive answers.
    
    The agent will search, analyze, and reason iteratively until it has
    sufficient confidence to provide a well-sourced comprehensive answer.
    """
    agent = IntelligentSearchAgent()
    
    result = await agent.run(
        user_query=request.query,
        max_iterations=request.max_iterations,
    )
    
    return result


@router.post(
    "/analyze",
    summary="AI-powered content extraction and analysis",
    response_model=ExtractedContent,
)
async def smart_analyze_content(request: AnalyzeRequest) -> ExtractedContent:
    """
    Extract relevant content from a URL using AI analysis.

    Uses llm model to analyze web content, extract only information
    relevant to the query, and assess content reliability with confidence scores.

    Recommended for quick, token-efficient content extraction.
    """
    analyzer = WebContentAnalyzer()
    result = await analyzer.analyze_url(request)
    return result


def register_mcp_tools(mcp: FastMCP):
    """Register MCP tools for this router"""
    mcp.tool()(intelligent_search)
    mcp.tool()(smart_analyze_content)