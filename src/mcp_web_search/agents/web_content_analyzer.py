"""
Basic Web Content Analyzer Agent

A simple agent that uses LangChain and OpenAI to extract relevant content
from a single web page based on a query, optimized for token efficiency.
"""

import os
from typing import Optional, cast

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, SecretStr

from ..routers.scraping import ScrapeRequest, fetch_web_content


class LLMExtraction(BaseModel):
    """Structured output from LLM for content analysis."""

    relevant_content: str = Field(
        description="Content relevant to the query in markdown format, modified based on reliability"
    )
    confidence_score: int = Field(
        description="0-100 percentage representing confidence in content reliability",
        ge=0,
        le=100,
    )
    short_answer: str = Field(
        description="Concise direct answer to the query based on extracted content"
    )
    remarks: str = Field(
        default="",
        description="Optional concise notes only for valuable insights about reliability, bias, or notable limitations"
    )


class AnalyzeRequest(BaseModel):
    """Request model for content analysis."""
    url: str = Field(..., description="URL to analyze for relevant content")
    query: str = Field(..., description="Query describing what content to extract")
    allow_cache: bool = Field(True, description="Whether to use cached results")


class ExtractedContent(LLMExtraction):
    """Final result combining scraped metadata with LLM analysis."""
    url: str = Field(..., description="The analyzed URL")
    title: str = Field(..., description="Page title")


class WebContentAnalyzer:
    """
    Simple web content analyzer that uses GPT-4o-mini to extract
    relevant content from a single URL based on user queries.
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the analyzer with OpenAI API key.

        Args:
            openai_api_key: OpenAI API key. If None, will try to get from environment.
        """
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
            )

        reasoning = {
            "effort": "low",  # 'low', 'medium', or 'high'
            "summary": None,  # 'detailed', 'auto', or None
        }

        self.llm = ChatOpenAI(
            model="gpt-5-mini",
            api_key=SecretStr(api_key),
            temperature=0.33,  # Low temperature for consistency
            reasoning=reasoning,
            output_version="responses/v1",
        )

        # Create structured LLM with Pydantic output
        self.structured_llm = self.llm.with_structured_output(LLMExtraction)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._get_system_prompt()),
                (
                    "human",
                    "Query: {query}\n\nWeb Page Title: {title}\n\nWeb Page Content:\n{content}\n\nExtract relevant content, assess its reliability, and modify based on confidence level.",
                ),
            ]
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for content extraction."""
        return """You are an expert content extraction agent. Your task is to:

1. Extract ONLY the content from the provided web page that is directly relevant to the user's query
2. Assess the reliability/confidence of the extracted content
3. Modify content based on reliability: compress low-confidence content, remove questionable content
4. Preserve important details and data points while being concise
5. Format the extracted content in clean markdown

Guidelines:
- Be extremely selective - only include content that directly answers or relates to the query
- Preserve specific facts, numbers, dates, and key details from reliable sources
- Remove navigation, ads, and irrelevant sections
- Use concise language but don't lose critical information
- Maintain markdown formatting for headers, links, lists, and emphasis to preserve structure

Content Modification Rules:
- High confidence (80-100%): Include full relevant content
- Medium confidence (50-79%): Include but compress/summarize the content
- Low confidence (20-49%): Heavily compress or mention briefly with caveats
- Very low confidence (0-19%): Remove content or replace with disclaimer

Confidence Assessment Factors:
- Source credibility (domain, authorship, citations)
- Content quality (factual, well-sourced, recent)
- Presence of supporting evidence
- Consistency and logical structure

Remarks Guidelines:
- Keep remarks empty unless there's valuable insight to share
- Only include concise notes about significant bias, reliability concerns, or data limitations
- Avoid generic statements about confidence - the score already captures that"""

    async def analyze_url(self, request: AnalyzeRequest) -> ExtractedContent:
        """
        Analyze a single URL and extract content relevant to the query.

        Args:
            request: AnalyzeRequest containing URL, query, and cache settings

        Returns:
            ExtractedContent with relevant information and confidence score
        """
        try:
            # Fetch content using cached scraper
            scrape_request = ScrapeRequest(
                urls=[request.url],
                allow_cache=request.allow_cache,
                include_image=False,
                output_format="markdown",
            )
            response = await fetch_web_content(scrape_request)

            if not response.results:
                raise ValueError("No results from scraper")

            result = response.results[0]
            raw_content = result.content
            title = result.title

            # Use structured LLM to extract relevant content
            chain = self.prompt | self.structured_llm
            llm_result = cast(
                LLMExtraction,
                await chain.ainvoke(
                    {"query": request.query, "title": title, "content": raw_content}
                ),
            )

            return ExtractedContent(
                url=request.url,
                title=title,
                relevant_content=llm_result.relevant_content,
                confidence_score=llm_result.confidence_score,
                short_answer=llm_result.short_answer,
                remarks=llm_result.remarks,
            )

        except Exception as e:
            # Create error result
            return ExtractedContent(
                url=request.url,
                title="Error",
                relevant_content=f"Failed to analyze {request.url}: {str(e)}",
                confidence_score=0,
                short_answer="Analysis failed",
            )
