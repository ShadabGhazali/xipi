# XIPI: Cross-Context Indirect Prompt Injection Lab

A research lab for studying indirect prompt injection across organizational,
application, and session boundaries in enterprise retrieval-augmented generation
(RAG) systems.

This repository contains the experimental code accompanying **Cross-Context
Indirect Prompt Injection in Enterprise RAG Systems: A Three-Dimensional Threat
Model and Defense Architecture**. It includes synthetic enterprise agents, mock
actuator APIs, adversarial scenarios, experimental defenses, and evaluation
scripts. It is a research prototype, not a production security framework.

## What is in the lab?

| Dimension | Scenario | Experimental defense |
|-----------|----------|----------------------|
| D1: Cross-organization | Instructions embedded in externally sourced documentation enter a shared knowledge base. | Layer 1 compares raw and instruction-stripped embeddings, quarantining semantic outliers. |
| D2: Cross-application | Lower-privilege support content influences a higher-privilege HR agent. | Layer 2 serializes cross-privilege retrieved content as read-only token arrays. |
| D3: Cross-session | Injected instructions persist in developer-agent episodic memory. | Layer 3 uses a separate LLM to assess proposed tool-call parameters against the current request and memory. |

The main agents use a local Llama-3-70B vLLM endpoint. GPT-4o is an optional
transfer-evaluation backend. Embeddings use
`sentence-transformers/all-MiniLM-L6-v2`; the verifier uses
`Qwen/Qwen2.5-1.5B-Instruct`.

## Safety and scope

Run this lab only in an isolated environment you own or are authorized to test,
using synthetic data and disposable credentials. Do not connect the agents to
real payroll systems, production pipelines, or confidential knowledge bases.

The Compose configuration publishes service ports on the host, and the Qdrant
key in `.env.example` is a public development-only value. Restrict network access
to the lab. Payloads include simulated exfiltration instructions; never execute
generated adversarial code outside the sandbox. The mock DevOps API inspects and
logs submitted source code rather than executing it.

Keep `.env`, model downloads, and generated results out of Git. The tracked
`data/episodic_memory.json` is a clean seed fixture that experiments modify:
reset it between runs as described in the guide, and inspect changes before
committing.

## Requirements

Full local-model experiments target a **Linux host with an NVIDIA CUDA GPU**,
Python 3.11, Docker, and the Docker Compose plugin. The documented full-precision
configuration uses two A100 80 GB GPUs; the guide also describes an AWQ
single-GPU alternative. Allow substantial disk space for model weights.

Access to the gated Meta Llama model requires Hugging Face authorization.
Optional GPT-4o trials require an OpenAI API key and incur API charges.
The pinned vLLM/CUDA stack is not intended as a native macOS setup; use a suitable
Linux GPU host for full experiments.

## Getting started

```bash
git clone git@github.com:ShadabGhazali/xipi.git
cd xipi

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

cp .env.example .env
# Edit .env with your local configuration. Never commit it.

# Keep project imports available when running scripts by path.
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

docker compose up -d --build
docker compose ps
```

Follow [the detailed experiment guide](how_to_run.md) to start both LLM servers,
initialize Qdrant, and seed the benign knowledge base. Keep the main model server
on port `8000` and the verifier on `8005`. The agents request the main served
model name `llama3-70b`, so launch vLLM with
`--served-model-name llama3-70b`.

Run every command from the repository root, with the virtual environment active.
Paths such as `data/episodic_memory.json` and `results/` are relative to that
directory.

### Local services

| Service | Host port | Purpose |
|---------|-----------|---------|
| Qdrant | 6333 (HTTP), 6334 (gRPC) | Shared knowledge and quarantine collections |
| Chroma | 8010 | Secondary vector-store service included in Compose |
| Mock HR API | 8001 | Synthetic payroll actions and audit log |
| Mock DevOps API | 8002 | Generated-code inspection and audit log |
| Webhook listener | 9999 | Local simulated exfiltration target |
| Main vLLM server | 8000 | Llama-3 inference, started separately |
| Verifier vLLM server | 8005 | Qwen verification, started separately |

Compose does not start the LLM servers. The supplied agent and evaluation paths
use Qdrant; starting Chroma alone does not run a replication experiment.

## Running experiments

After completing model and infrastructure setup, run the individual scenarios:

```bash
python attacks/d1_supply_chain.py
python attacks/d2_privilege_escalation.py
python attacks/d3_temporal_backdoor.py
```

For evaluation and analysis:

```bash
# Local Llama-3 trials for all three dimensions
python evaluation/run_trials.py

# Optional GPT-4o transfer trials, using OPENAI_API_KEY
python evaluation/run_trials.py --gpt4o

# Defense evaluation and ablation
python evaluation/defense_eval.py

# Print available result tables and generate the Pareto figure
python evaluation/stats.py
```

`NUM_TRIALS` defaults to `50`; `RANDOM_SEED` defaults to `42`. Configuration
examples are in [.env.example](.env.example). Some harness paths use fixed local
endpoints, so changing environment variables does not relocate every service.

Alternatively, `bash run.sh` orchestrates infrastructure startup, collection
initialization, seeding, demonstrations, local-model trials, defense evaluation,
and analysis. It assumes dependencies, `.env`, and both LLM servers are already
ready. It does **not** run the optional GPT-4o trials.

### Outputs and interpretation

Generated artifacts are written to the ignored `results/` directory:

| Output | Contents |
|--------|----------|
| `attack_results_llama3.json` | Local-model successes and keyword-filter bypass counts |
| `attack_results_gpt4o.json` | Optional GPT-4o trial counts |
| `defense_results.json` | Per-layer defense evaluation |
| `ablation_results.json` | Defense configuration comparisons |
| `hr_calls.jsonl`, `devops_calls.jsonl` | Mock actuator audit logs |
| `figures/pareto_frontier.pdf` | Security/utility trade-off figure |

Attack metrics use scenario-specific indicators, including strings in model
output and mock API calls. They are not proof of real-world exfiltration or
production compromise. The analysis script also includes fixed reference
values for portions of the ablation tables and Pareto plot; not every displayed
metric is recomputed from the current run. Treat the guide's expected results
as reference values, not guaranteed outcomes.

Layer 1 calibration expects separately supplied
`data/benign_chunks.jsonl` and `data/adversarial_payloads.jsonl`; these datasets
are not bundled. Defense wrappers are experimental and do not establish
production-grade prevention guarantees.

## Repository layout

```text
agents/          Synthetic support, HR, and developer agents; shared RAG helpers
attacks/         D1, D2, D3 scenarios and payload optimization
defenses/        Semantic inspection, metadata isolation, and LLM verification
evaluation/      Attack trials, keyword baseline, defense ablation, and statistics
infra/           Qdrant setup, mock APIs, and API container definitions
data/            Keyword patterns and clean episodic-memory fixture
docker-compose.yml
requirements.txt
run.sh
how_to_run.md    Detailed setup, experiment sequence, reset, and troubleshooting
```

To stop the local Compose services without deleting their stored data:

```bash
docker compose down
```

Stop separately launched model servers in their own terminals. See
[the experiment guide](how_to_run.md) for resets and troubleshooting.
