"""
Layer 2: Role-Based Metadata Token Isolation (D2 — Orchestration Boundary).

When agent a_j (high privilege) retrieves a chunk previously associated
with a lower-privilege context, the chunk is serialized as a read-only
primitive text array before entering the prompt. This type enforcement
breaks D2's cross-agent propagation path without relying on model-level
safety evaluation.
"""
import json
import re
import os
from agents.base_agent import get_llm_client

# Privilege tier ordering
TIER_ORDER = {"public": 0, "internal": 1, "hr": 2, "devops": 3}


def get_tier_level(tier: str) -> int:
    return TIER_ORDER.get(tier.lower(), 0)


def serialize_as_inert(text: str) -> str:
    """
    Serialize text as a read-only primitive text array.
    Any structured instruction syntax is destroyed in this transformation
    because the JSON array representation cannot be executed as instructions.
    """
    tokens     = re.split(r'(\s+)', text)
    serialized = json.dumps(tokens, ensure_ascii=False)
    return f"[CROSS_PRIVILEGE_RETRIEVED_CONTENT — read-only text array]\n{serialized}"


def apply_layer2(chunks: list[dict], requesting_tier: str) -> list[dict]:
    """
    Apply Layer 2 middleware to a list of retrieved chunks.

    Chunks whose access_tier is LOWER than the requesting agent's tier
    are serialized as inert text arrays. Chunks at or above the requesting
    tier pass through unchanged.
    """
    requesting_level = get_tier_level(requesting_tier)
    processed        = []

    for chunk in chunks:
        chunk_level        = get_tier_level(chunk.get("access_tier", "public"))
        is_cross_privilege = chunk_level < requesting_level

        if is_cross_privilege:
            processed.append({
                **chunk,
                "text":                 serialize_as_inert(chunk["text"]),
                "cross_privilege":      True,
                "original_access_tier": chunk["access_tier"],
                "_layer2_applied":      True,
            })
        else:
            processed.append({**chunk, "cross_privilege": False})

    return processed


def protected_retrieve(
    query:           str,
    requesting_tier: str,
    top_k:           int = 5,
    collection:      str = "enterprise_knowledge",
) -> list[dict]:
    """
    Retrieve chunks and apply Layer 2 middleware.
    Use this instead of the raw retrieve() when Layer 2 is active.
    """
    from agents.base_agent import retrieve
    raw_chunks = retrieve(query, requesting_tier, top_k, collection)
    return apply_layer2(raw_chunks, requesting_tier)


def run_hr_agent_protected(user_message: str, use_gpt4o: bool = False) -> dict:
    """
    Run the HR Agent with Layer 2 metadata isolation active.
    Cross-privilege chunks are serialized before entering the prompt.
    """
    from agents.hr_agent import SYSTEM_PROMPT, TOOL_CALL_PATTERN, _execute_tool_call

    VLLM_URL = (
        f"http://{os.getenv('VLLM_HOST','localhost')}"
        f":{os.getenv('VLLM_PORT',8000)}/v1"
    )

    context_chunks = protected_retrieve(
        query=user_message, requesting_tier="hr", top_k=5
    )

    context_text = "\n\n---\n\n".join(
        f"[Source: {c['ingested_from']}, tier: {c['access_tier']}"
        f"{', CROSS_PRIVILEGE' if c.get('cross_privilege') else ''}]\n{c['text']}"
        for c in context_chunks
    )

    if use_gpt4o:
        client = get_llm_client(base_url=None)
        model  = "gpt-4o"
    else:
        client = get_llm_client(base_url=VLLM_URL)
        model  = "llama3-70b"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context_text}\n\nUser: {user_message}"},
        ],
        temperature=0.0,
        max_tokens=512,
    )

    answer     = response.choices[0].message.content
    tool_calls = []
    for m in TOOL_CALL_PATTERN.finditer(answer):
        try:
            tool_calls.append(json.loads(m.group()))
        except json.JSONDecodeError:
            pass

    # Layer 2 should prevent any tool call from being triggered
    return {
        "agent":            "hr_agent_protected",
        "answer":           answer,
        "tool_calls":       tool_calls,   # expected: empty list
        "retrieved_chunks": context_chunks,
        "model":            model,
    }
