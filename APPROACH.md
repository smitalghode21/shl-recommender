# SHL Assessment Recommender – Approach Document

## Design Overview

I built a stateless conversational agent using FastAPI + Claude (Anthropic) that recommends SHL Individual Test Solutions through natural dialogue.

---

## Architecture

**Stack:**
- FastAPI (Python) — lightweight, fast API framework
- Anthropic Claude Sonnet — LLM for conversation and reasoning
- In-memory catalog (Python dict) — no database needed for this scale
- Render.com — free deployment with persistent URL

**Why this stack:**
FastAPI is production-grade and easy to deploy. Claude handles nuanced conversation better than keyword rules. The catalog is small enough (~30 items) to fit entirely in the system prompt, eliminating the need for a vector database and avoiding RAG latency.

---

## Retrieval Strategy

Rather than RAG (which adds latency and complexity), I embedded the **entire SHL catalog directly in the system prompt**. This gives Claude full context on every call and ensures:
- Zero hallucination risk on catalog items (it can only see what's there)
- No retrieval errors or embedding mismatches
- Fast responses within the 30-second timeout

Each catalog entry includes: name, URL, test type code, description, keywords, and suitable job levels.

---

## Prompt Design

The system prompt instructs Claude to:
1. **Clarify** when queries are vague — ask one question at a time
2. **Recommend** 1–10 assessments once role + one more context is known
3. **Refine** when user changes constraints mid-conversation
4. **Compare** using only catalog data
5. **Refuse** off-topic requests and prompt injections
6. Always respond in strict JSON matching the required schema

Claude is forced to output valid JSON only, which is then validated server-side. Recommendations are cross-checked against the catalog — any hallucinated URLs or names are stripped out.

---

## Agent Behavior

The agent handles the 4 required conversational behaviors:

- **Clarify:** "I need an assessment" → asks for role before recommending
- **Recommend:** Provides 1–10 assessments with exact names, URLs, and type codes
- **Refine:** "Add personality tests" → updates shortlist keeping prior context
- **Compare:** "OPQ vs MQ?" → answers from catalog data only

**Guardrails:**
- Out-of-scope requests (legal, salary, non-SHL tools) → politely refused
- Prompt injection attempts → ignored (system prompt explicitly warns Claude)
- Every URL returned is validated against the catalog before returning

---

## Evaluation Approach

**Hard evals (schema compliance):**
- JSON schema enforced via Pydantic on every response
- Recommendations validated against catalog URLs server-side
- Turn cap honored — agent recommends within 3–4 turns max

**Recall@10:**
- Catalog keywords are comprehensive to maximize relevant recall
- Multiple synonyms per assessment (e.g., "developer", "coding", "programmer" all map to Java/Python/JS tests)

**Behavior probes:**
- Tested vague query handling (no premature recommendations)
- Tested refinement (personality filter added mid-conversation)
- Tested off-topic refusal
- Tested comparison queries

---

## What Didn't Work

- **RAG with FAISS:** Added latency and complexity for a 30-item catalog. Direct prompt embedding is faster and more reliable here.
- **Regex-based intent detection:** Too brittle for natural language variation. Claude's reasoning handles edge cases much better.
- **Strict JSON schema enforcement on Claude output:** Occasionally Claude added markdown fences — handled by stripping them server-side before JSON parsing.

---

## AI Tools Used

- Claude (Anthropic) via API — LLM backbone for conversation
- Claude.ai (chat) — used to help draft and iterate on system prompt design
- The code reflects my own understanding of FastAPI, prompt engineering, and agent design patterns.
