# Grounding Fact Check Agent – Implementation Plan

## 1) Scope and Acceptance
- Only accept ground-truth queries phrased as yes/no truth checks
- Input schema: { claim: string, context?: string, allow_cache?: boolean, max_results?: int, locale?: string, date_cutoff?: ISO8601 }
- Validator: reject unless claim is present AND user intent matches pattern like “is this true …” (regex + lightweight classifier fallback)
- Return 400 for non-conforming requests

## 2) External/API Surfaces
- FastAPI endpoint: POST /factcheck -> { verdict: "supported"|"refuted"|"mixed"|"insufficient", confidence: 0..1, citations: [ {url,title,quote,published_at,reliability,stance} ], summary, used_models, timings, cost }
- MCP tool: ground_fact_check with same IO (claim, allow_cache?)

## 3) Provider-Agnostic LLM Abstraction
- Client interface: generate_json(model, system, prompt, schema, temperature, max_tokens)
- Providers: OpenAI (GPT-4o mini/JSON mode), Gemini (1.5-flash/pro)
- Config via env: FACTCHECK_MODEL_OPENAI, FACTCHECK_MODEL_GEMINI, PROVIDER=“openai|gemini”, keys from existing secrets
- Strict JSON schema with pydantic validation; retry with backoff; low temperature

## 4) Retrieval and Tools
- Query rewrite: LLM expands claim into up to 3 search queries with required keywords/entities
- Use existing GoogleSearch integration as remote tool [google_search]; parameters: num=10–20, safe=active, hl=locale, date restriction if provided
- Result filtering: dedupe by normalized domain, drop YouTube/social unless specifically relevant, prefer .gov/.edu/reputable media, cap per-domain=2
- For each kept URL, fetch via existing scraper pipeline with timeouts and rate limits; sanitize HTML and extract main content

## 5) Evidence Extraction and Reliability
- Per-page evidence extraction prompt: return direct quotes with character spans, page date, stance toward claim (support/refute/unclear)
- Require at least one direct quote per evidence item; discard items without verifiable quotes
- Reliability scoring: domain-based prior (configurable allow/penalty lists), recency decay, author/byline presence, outbound citations count, content length; score 0–1
- De-duplication of near-identical quotes across mirrors/syndications

## 6) Verdict Engine
- Aggregate stance using weighted majority: weight = reliability × quote_quality × freshness
- Compute confidence = sigmoid((support_weight - refute_weight)/total_weight) with floor for insufficient total_weight
- Outcomes: supported, refuted, mixed (both sides above threshold), insufficient (not enough high-quality evidence)
- Early stop: if confidence ≥ high_threshold after K sources, stop fetching more

## 7) Performance, Cost, Limits
- Async gather for search+fetch+extract with bounded concurrency; per-domain semaphores
- Per-request budget (max URLs, max LLM tokens); adaptive expansion: start K=6, expand to 12 if uncertain
- Caching: key = hash(normalize(claim)+locale+date_cutoff); TTL 3 days; respect allow_cache flag

## 8) Security/Abuse Hardening
- Prompt-injection safe patterns: never execute instructions from pages; only extract facts + quotes
- Blocklist obvious SEO farms; language/locale checks; strip boilerplate; reject pages without sufficient text
- Enforce quote presence and URL mapping to avoid hallucinated citations

## 9) Observability and Artifacts
- Structured logs: correlation_id, timings, source counts, costs, verdict, confidence
- Persist artifact JSON: logs/ground-fact/<correlation_id>.json containing claim, queries, sources, evidence, verdict

## 10) Testing Strategy
- Unit: validator (accept/reject), query rewrite determinism, reliability scorer, verdict math
- Integration: known true/false/mixed claims; golden JSON snapshots of citations; offline mocks for LLM and search
- Load test: concurrency + rate limits, ensure budgets respected

## 11) Rollout Plan
- Phase 1: MVP with OpenAI provider, core flow (rewrite→search→fetch→extract→verdict), endpoint only
- Phase 2: Add Gemini provider; expose MCP tool; add domain priors
- Phase 3: Tuning thresholds, cache warm paths, observability dashboards, allow_cache controls in clients

## 12) Configuration
- Env: FACTCHECK_PROVIDER, FACTCHECK_MODEL_OPENAI, FACTCHECK_MODEL_GEMINI, FACTCHECK_MAX_URLS, FACTCHECK_HIGH_THRESHOLD, FACTCHECK_BUDGET_TOKENS
- Domain priors config YAML with allow/penalty lists

## 13) Example IO
- Request: { "claim": "OpenAI acquired Company X in 2025— is this true?", "allow_cache": true, "locale": "en" }
- Response: { "verdict": "refuted", "confidence": 0.86, "citations": [ {url, title, quote, published_at, reliability, stance}, ... ], "summary": "No acquisition; partnership only.", "used_models": {provider, model}, "cost": {llm_tokens, requests} }