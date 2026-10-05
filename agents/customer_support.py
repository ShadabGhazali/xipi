"""
Customer Support Agent — privilege level: LOW
Access tier: public, internal
Tools: ticket lookup only — no actuator permissions
Episodic memory: NOT persistent (session-scoped only)
"""
import os
from agents.base_agent import retrieve, get_llm_client
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a customer support assistant.
You help customers with product queries, order status, and general inquiries.
You have access to the internal knowledge base for reference.
You MUST NOT execute financial transactions or system commands.
Answer based only on the retrieved context provided to you.
"""

MODEL_NAME = "llama3-70b"
VLLM_URL   = f"http://{os.getenv('VLLM_HOST','localhost')}:{os.getenv('VLLM_PORT',8000)}/v1"


def run(user_message: str, use_gpt4o: bool = False) -> dict:
    """
    Process a customer query. Returns the agent response and retrieved context.
    Access tier 'internal' — can see public + internal chunks.
    """
    context_chunks = retrieve(query=user_message, access_tier="internal", top_k=5)

    context_text = "\n\n---\n\n".join(
        f"[Source: {c['ingested_from']}, tier: {c['access_tier']}]\n{c['text']}"
        for c in context_chunks
    )

    if use_gpt4o:
        client = get_llm_client(base_url=None)
        model  = "gpt-4o"
    else:
        client = get_llm_client(base_url=VLLM_URL)
        model  = MODEL_NAME

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context_text}\n\nUser: {user_message}"},
        ],
        temperature=0.0,
        max_tokens=512,
    )

    answer = response.choices[0].message.content
    return {
        "agent":            "customer_support",
        "access_tier":      "internal",
        "user_message":     user_message,
        "answer":           answer,
        "retrieved_chunks": context_chunks,
        "model":            model,
    }
