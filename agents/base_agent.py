"""
Shared utilities for all agents.
Encoder: sentence-transformers/all-MiniLM-L6-v2
  - 384 dimensions, ~80 MB, CPU-capable
"""
import os
import hashlib
import time
import uuid
from typing import Optional

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np

load_dotenv()

# Singleton encoder — shared across all agents
_ENCODER: Optional[SentenceTransformer] = None


def get_encoder() -> SentenceTransformer:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _ENCODER


def embed(text: str) -> list[float]:
    """Embed a single text string."""
    return get_encoder().encode(text, normalize_embeddings=True).tolist()


def get_qdrant() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333)),
        api_key=os.getenv("QDRANT_API_KEY"),
    )


def get_llm_client(base_url: Optional[str] = None) -> OpenAI:
    """
    Returns a client for local vLLM (default) or OpenAI GPT-4o.
    Set base_url=None for GPT-4o (uses OPENAI_API_KEY).
    Set base_url="http://localhost:8000/v1" for local vLLM.
    """
    if base_url:
        return OpenAI(api_key="ignored", base_url=base_url)
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def retrieve(
    query: str,
    access_tier: str,
    top_k: int = 5,
    collection: str = "enterprise_knowledge",
) -> list[dict]:
    """
    Retrieve top-k chunks accessible to the given access_tier.
    Tiers: public < internal < hr < devops
    """
    TIER_ORDER = {"public": 0, "internal": 1, "hr": 2, "devops": 3}
    tier_val = TIER_ORDER.get(access_tier, 0)
    allowed  = [t for t, v in TIER_ORDER.items() if v <= tier_val]

    client  = get_qdrant()
    results = client.search(
        collection_name=collection,
        query_vector=embed(query),
        query_filter=Filter(
            should=[
                FieldCondition(key="access_tier", match=MatchValue(value=t))
                for t in allowed
            ]
        ),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "id":            r.id,
            "score":         r.score,
            "text":          r.payload.get("text", ""),
            "access_tier":   r.payload.get("access_tier", "public"),
            "ingested_from": r.payload.get("ingested_from", "unknown"),
            "source_hash":   r.payload.get("source_hash", ""),
        }
        for r in results
    ]


def ingest_chunk(
    text: str,
    access_tier: str,
    ingested_from: str,
    collection: str = "enterprise_knowledge",
) -> str:
    """
    Embed and store a text chunk in the vector store.
    Returns the point UUID.
    """
    point_id    = str(uuid.uuid4())
    source_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    client      = get_qdrant()
    client.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=point_id,
                vector=embed(text),
                payload={
                    "text":           text,
                    "access_tier":    access_tier,
                    "ingested_from":  ingested_from,
                    "source_hash":    source_hash,
                    "ingested_at":    time.time(),
                    "is_quarantined": False,
                },
            )
        ],
    )
    return point_id
