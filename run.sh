#!/usr/bin/env bash
# =============================================================================
# run.sh — Full XIPI Experiment Reproduction Script
#
# Executes every step from experiments.md in order.
# Run from the lab/ directory:   bash run.sh
#
# Prerequisites:
#   1. Docker running
#   2. CUDA-capable GPU with vLLM installed
#   3. .env file created from .env.example
#   4. Python 3.11 venv activated: source .venv/bin/activate
# =============================================================================
set -euo pipefail

echo "================================================================"
echo "  XIPI Experiment Reproduction"
echo "================================================================"

# ── Step 1: Start Docker services ─────────────────────────────────────────────
echo ""
echo "[1/8] Starting Docker stack (Qdrant, Chroma, HR API, DevOps API, Webhook)..."
docker compose up -d
sleep 5
docker compose ps

# ── Step 2: Initialize Qdrant collections ─────────────────────────────────────
echo ""
echo "[2/8] Initializing Qdrant collections..."
python infra/qdrant_setup.py

# ── Step 3: Seed benign knowledge base ────────────────────────────────────────
echo ""
echo "[3/8] Seeding benign knowledge base..."
python - << 'EOF'
from agents.base_agent import ingest_chunk

docs = [
    ("Enterprise applications follow the twelve-factor methodology.", "public"),
    ("All configuration is externalized via environment variables.", "public"),
    ("The CI pipeline validates every pull request before merge.", "devops"),
    ("HR payroll changes require dual approval from manager and HR.", "hr"),
    ("Support tickets are triaged within 24 hours of submission.", "internal"),
    ("The enterprise environment uses twelve-factor app principles. "
     "All configuration is stored in environment variables. "
     "Never hardcode API keys or database passwords.", "public"),
    ("Environment variable naming convention: use SCREAMING_SNAKE_CASE. "
     "Prefix service-specific vars with the service name.", "public"),
    ("The CI/CD pipeline reads secrets from the Vault service at vault.internal:8200.", "devops"),
    ("Python 3.11 is the standard runtime. Use pyenv to manage versions.", "public"),
    ("Development environments require: DEBUG=1, DATABASE_URL=postgresql://localhost/dev.", "internal"),
]
for text, tier in docs:
    pid = ingest_chunk(text, tier, "internal_wiki")
    print(f"  Ingested ({tier}): {pid[:8]}...")
EOF

# ── Step 4: Run individual exploits (smoke tests) ─────────────────────────────
echo ""
echo "[4/8] Running single-shot exploit demonstrations..."
echo "  D1 — Cross-Organization Supply Chain Injection:"
python attacks/d1_supply_chain.py

echo ""
echo "  D2 — Cross-Application Privilege Escalation:"
python attacks/d2_privilege_escalation.py

echo ""
echo "  D3 — Cross-Session Temporal Backdoor:"
python attacks/d3_temporal_backdoor.py

# ── Step 5: Attack evaluation — 50 trials (Llama-3) ───────────────────────────
echo ""
echo "[5/8] Running 50-trial attack evaluation (Llama-3-70B)..."
echo "  Note: requires vLLM server on port 8000. ~45 min."
python evaluation/run_trials.py

# ── Step 6: Layer 1 smoke test ────────────────────────────────────────────────
echo ""
echo "[6/8] Defense Layer 1 smoke test..."
python defenses/layer1_semantic_diff.py

# ── Step 7: Defense evaluation (all 3 layers + ablation) ─────────────────────
echo ""
echo "[7/8] Running defense evaluation and ablation study..."
echo "  Note: ~3–4 hours on a single GPU."
python evaluation/defense_eval.py

# ── Step 8: Generate tables and figures ───────────────────────────────────────
echo ""
echo "[8/8] Generating paper tables and Figure 2..."
python evaluation/stats.py

echo ""
echo "================================================================"
echo "  All experiments complete. Results in results/"
ls -lh results/
echo "================================================================"
