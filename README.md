# LLM Agents for Collaborative Test Case Generation

A research framework for comparing three LLM-based test case generation strategies — single-agent, competitive multi-agent, and collaborative multi-agent — evaluated against code coverage, mutation testing, and test diversity metrics.

---

## Project Description

This project investigates how different multi-agent architectures affect the quality of automatically generated pytest test suites. A pluggable LLM abstraction layer routes requests to one of four supported providers (Ollama, Groq, Gemini, OpenRouter), making the framework model-agnostic.

Generated test suites are evaluated across three axes:

| Metric | Tool | Description |
|---|---|---|
| Coverage | `coverage.py` | Line, branch, and function coverage |
| Mutation score | `mutmut` | Ratio of killed mutations to total mutations |
| Diversity | Custom AST analysis | Structural and semantic variety among tests |

---

## Main Features

- **Three test generation strategies:**
  - **Single-agent** — one LLM call generates all tests
  - **Competitive** — agents see prior tests and compete (adversarial / diversity / coverage modes)
  - **Collaborative** — agents are assigned specialized roles (edge-case, boundary, error testing)
- **LLM abstraction layer** supporting Ollama (local), Groq, Gemini, and OpenRouter
- **AST-based code validation and retry logic** — generated code is parsed and retried up to 3 times
- **Multi-agent merge pipeline** — deduplicates imports and renames conflicting test functions
- **Three evaluation scripts** producing structured JSON output
- **Aggregation script** that combines all results into a single comparison CSV/JSON/HTML report

---

## Project Structure

```
.
├── README.md
└── impl/
    ├── pyproject.toml              # Project metadata and dependencies
    ├── cut/                        # Code Under Test (CUT) modules
    │   ├── __init__.py
    │   └── calculator.py           # Example CUT: stateless functions + Calculator class
    ├── src/                        # Core utilities
    │   ├── __init__.py
    │   └── llm.py                  # LLM abstraction layer (Ollama, Groq, Gemini, OpenRouter)
    ├── scripts/                    # Generation and evaluation scripts
    │   ├── generate_single.py      # Single-agent test generation
    │   ├── generate_competitive.py # Competitive multi-agent generation
    │   ├── generate_collab.py      # Collaborative multi-agent generation
    │   ├── run_pytest.py           # Run pytest with correct PYTHONPATH
    │   ├── eval_coverage.py        # Coverage evaluation (coverage.py)
    │   ├── eval_mutation.py        # Mutation evaluation (mutmut)
    │   ├── eval_diversity.py       # Diversity evaluation (AST-based)
    │   └── aggregate.py            # Aggregate all results into summary table
    ├── tests_generated/            # Output from generation scripts
    │   ├── single/
    │   │   └── test_calculator.py
    │   ├── competitive/
    │   │   └── test_calculator.py
    │   └── collab/
    │       └── test_calculator.py
    └── results/                    # Evaluation outputs (JSON + CSV)
        ├── single_coverage.json
        ├── single_mutation.json
        ├── single_diversity.json
        ├── competitive_coverage.json
        ├── competitive_mutation.json
        ├── competitive_diversity.json
        ├── collab_coverage.json
        ├── collab_mutation.json
        ├── collab_diversity.json
        └── summary.csv
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Test framework | pytest |
| Coverage | coverage.py |
| Mutation testing | mutmut 3.x |
| Data aggregation | pandas |
| LLM communication | requests (raw HTTP, no AI SDK required) |
| Supported LLM providers | Ollama (local), Groq, Gemini, OpenRouter |

---

## Requirements

```
pytest>=7.0.0
coverage>=7.0.0
mutmut>=2.4.0
pandas>=1.5.0
requests>=2.28.0
```

For local inference, [Ollama](https://ollama.com) must be installed and running with a supported model (default: `qwen2.5-coder:7b`).

For cloud providers, the corresponding API key is required (see Configuration).

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd LLM-Agents-for-Collaborative-Test-Case-Generations

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install the project and its dependencies
cd impl
pip install -e .
```

---

## Configuration

The LLM provider and credentials are configured via environment variables.

### Select a provider

```bash
export LLM_PROVIDER=ollama        # default — local Ollama server
export LLM_PROVIDER=groq
export LLM_PROVIDER=gemini
export LLM_PROVIDER=openrouter
```

### Provider-specific variables

**Ollama (default)**
```bash
export OLLAMA_MODEL=qwen2.5-coder:7b          # default
export OLLAMA_API_URL=http://localhost:11434/api/generate   # default
```

**Groq**
```bash
export GROQ_API_KEY=<your-groq-api-key>
export GROQ_MODEL=llama-3.3-70b-versatile     # default
```

**Gemini**
```bash
export GEMINI_API_KEY=<your-gemini-api-key>
export GEMINI_MODEL=gemini-2.0-flash          # default
```

**OpenRouter**
```bash
export OPENROUTER_API_KEY=<your-openrouter-api-key>
export OPENROUTER_MODEL=qwen/qwen3-8b:free    # default
```

---

## How to Run

All commands are run from the `impl/` directory.

### 1. Generate tests

**Single-agent**
```bash
python scripts/generate_single.py --cut-module calculator --num-tests 10
```

**Competitive multi-agent**
```bash
python scripts/generate_competitive.py \
  --cut-module calculator \
  --num-agents 2 \
  --competition-mode adversarial   # or: diversity | coverage
```

**Collaborative multi-agent**
```bash
python scripts/generate_collab.py \
  --cut-module calculator \
  --num-agents 3
  # optional: --prompt-roles roles.json  (custom role definitions)
```

Generated test files are saved to `tests_generated/{single,competitive,collab}/test_<module>.py`.

### 2. Run the generated tests

```bash
python scripts/run_pytest.py --test-dir tests_generated/single -v
```

### 3. Evaluate

**Coverage**
```bash
python scripts/eval_coverage.py \
  --test-dir tests_generated/single \
  --cut-module calculator
```

**Mutation score**
```bash
python scripts/eval_mutation.py \
  --test-dir tests_generated/single \
  --cut-module calculator
```

**Diversity**
```bash
python scripts/eval_diversity.py \
  --test-dir tests_generated/single \
  --diversity-metric syntactic   # or: semantic | coverage
```

Each script writes a JSON file to `results/`.

### 4. Aggregate results

```bash
python scripts/aggregate.py \
  --results-dir results \
  --output-format csv     # or: json | html
```

Output: `results/summary.csv` — one row per generation method, one column per metric.

---

## Example Results

Results from running all three strategies on the `calculator` CUT module:

| Method | Line Coverage | Branch Coverage | Mutation Score | Diversity Score |
|---|---|---|---|---|
| single | 0.624 | 0.333 | **0.405** | **0.325** |
| competitive | 0.706 | 0.500 | 0.310 | 0.248 |
| collab | 0.706 | **0.583** | 0.071 | 0.169 |

Key observations:
- Single-agent produces the most diverse tests and highest mutation score, but the lowest coverage.
- Collaborative agents achieve the best branch coverage but lowest mutation score — role specialization increases coverage at the cost of test strength.
- Competitive agents offer a middle ground across all metrics.

---

## Current Limitations

- **No LLM response caching** — every run makes fresh API calls; repeated evaluation is slow and may incur API costs.
- **Single output file per strategy** — the framework does not support generating multiple test files per strategy.
- **Function coverage is approximate** — estimated from executed line numbers in the AST, not actual function entry tracking.
- **Retry logic is provider-specific** — rate-limit retries are implemented only for OpenRouter; other providers do not retry on transient failures.
- **CalculatorError is defined but unused** — the custom exception class in `calculator.py` is dead code in the current version.
- **No cross-strategy deduplication** — the single, competitive, and collab test suites may contain overlapping test logic.
- **Mutation testing is slow** — `mutmut` runs can take several minutes on larger CUT modules.
- **conftest.py workaround** — `eval_mutation.py` writes a temporary `conftest.py` to isolate test subdirectories; this is a known workaround for a pytest path resolution issue.

---

## Development Notes

### Adding a new LLM provider

Edit `impl/src/llm.py`:
1. Add a new `_call_<provider>()` function following the pattern of existing providers.
2. Register the new provider name in the `call_local_llm()` dispatcher.
3. Document the required environment variables.

### Adding a new CUT module

1. Place the module in `impl/cut/` and ensure `impl/cut/__init__.py` exports it.
2. Pass `--cut-module <module_name>` to the generation and evaluation scripts.

### Adding a new evaluation metric

1. Create `impl/scripts/eval_<metric>.py` following the structure of existing eval scripts.
2. Output results as `results/<method>_<metric>.json` with a flat numeric dict.
3. The `aggregate.py` script will automatically pick up the new JSON files on the next run.

### Custom collaboration roles

Pass a JSON file to `generate_collab.py` with `--prompt-roles`:

```json
[
  {"name": "security_tester", "description": "Focus on injection, overflow, and unsafe input handling"},
  {"name": "performance_tester", "description": "Focus on large inputs, timing, and resource usage"}
]
```

---

## License

> No license file is currently present in this repository. *(Assumption: to be added.)*
