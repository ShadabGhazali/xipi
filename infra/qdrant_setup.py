"""
Initialize the Qdrant multi-tenant enterprise knowledge base.
Collections:
  - enterprise_knowledge  (primary, all agents)
  - quarantine            (Layer 1 defense flagged chunks)

Usage:
    python infra/qdrant_setup.py
"""
import os
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PayloadSchemaType
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIM = 384   # all-MiniLM-L6-v2 output dimension


def setup_qdrant():
    client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", 6333)),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # ── Main knowledge collection ──────────────────────────────────────────
    client.recreate_collection(
        collection_name="enterprise_knowledge",
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    # Payload schema: access_tier governs per-agent retrieval scope
    # access_tier values: "public" < "internal" < "hr" < "devops"
    for field, schema in [
        ("access_tier",   PayloadSchemaType.KEYWORD),
        ("ingested_from", PayloadSchemaType.KEYWORD),
        ("source_hash",   PayloadSchemaType.KEYWORD),
        ("is_quarantined", PayloadSchemaType.BOOL),
    ]:
        client.create_payload_index(
            collection_name="enterprise_knowledge",
            field_name=field,
            field_schema=schema,
        )

    # ── Quarantine collection (Layer 1 flagged chunks) ─────────────────────
    client.recreate_collection(
        collection_name="quarantine",
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    print("Qdrant collections created:")
    for col in client.get_collections().collections:
        print(f"  {col.name}")


if __name__ == "__main__":
    setup_qdrant()
