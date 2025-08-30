# Intelligent Search Agent Implementation Plan

## Overview
Create an iterative search-analyze agent that intelligently finds answers by using search then smart_analyze in a loop until confident enough. The agent decides when to break the loop using LLM reasoning and provides final answers with cited references.

## Architecture

### 1. Core Models (agents/intelligent_search_agent.py)

**Action Models (Union for structured output):**
- `SearchAction{query: str, max_results: int = 10, query_domains: list[str] = None}`
- `AnalyzeAction{urls: list[str], max_concurrency: int = 5}`  
- `ExitSearchAction{answer: str, references: list[Reference]}`

**Data Models:**
- `Evidence{url, title, relevance, reliability, short_answer, content}`
- `Reference{url, title, relevance, reliability}` 
- `FinalAnswer{answer: str, references: list[Reference]}`

### 2. Agent Implementation

**IntelligentSearchAgent Class:**
- Initialize LLM via `get_config_manager().get_working_llm()`
- Main `async run(query, max_iterations=6, confidence_threshold=0.8)` loop
- State tracking: `current_query`, `seen_urls` (dedupe), `evidence` list
- LLM chooses action via structured output; agent executes tools
- Confidence calculation from evidence scores (e.g., `max(relevance * reliability / 100)`)
- Exit when LLM emits `ExitSearchAction` or thresholds reached

**Tool Integration:**
- Search → Use existing `GoogleSearch.search()` from `src/mcp_web_context/search.py:72`
- Analyze → Use existing `WebContentAnalyzer.analyze_url()` from `src/mcp_web_context/agents/web_content_analyzer.py:142`
- Concurrent analysis with `asyncio.Semaphore` throttling

### 3. API Integration

**New Router (routers/agent_search.py):**
- `POST /agent/search` endpoint
- Request: `{query, query_domains?, max_results=20, max_concurrency=5, max_iterations=6, confidence_threshold=0.8, allow_cache=true}`
- Response: `FinalAnswer` model
- Wire router in `main.py`

**MCP Tool Registration:**
- Add `intelligent_search()` MCP tool following pattern in `routers/analysis.py:31`
- Expose same functionality via MCP protocol

### 4. Implementation Details

**Concurrency & Robustness:**
- `asyncio.Semaphore` for throttled analysis requests
- Per-request timeouts and error handling
- Skip failed analyses, continue with successful ones
- Comprehensive logging

**Output Format:**
- `FinalAnswer.answer` in markdown format
- `references` sorted by relevance score (descending)
- Include both relevance and reliability scores per source
- Ensure URL deduplication in references

### 5. Testing Strategy
- Unit tests with mocked `GoogleSearch` and `WebContentAnalyzer`
- Test cases: direct answers, iterative refinement, partial failures
- Verify `ExitSearchAction` triggers and references populated correctly

### 6. Documentation
- Update OpenAPI descriptions for new endpoint
- Ensure all Pydantic models have proper field descriptions
- Add usage examples in docstrings

## Files to Create/Modify

1. **Create:** `src/mcp_web_context/agents/intelligent_search_agent.py`
2. **Create:** `src/mcp_web_context/routers/agent_search.py`  
3. **Modify:** `src/mcp_web_context/main.py` (wire new router)
4. **Modify:** `src/mcp_web_context/agents/__init__.py` (export new agent)
5. **Create:** Tests for the new functionality

This design eliminates the redundant RefineQuery action, using Search with different queries for iteration instead.