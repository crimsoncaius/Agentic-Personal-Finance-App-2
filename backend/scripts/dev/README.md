# Development Scripts

This directory contains development and testing scripts for the Agentic Personal Finance App.

## Directory Structure

- `input/` - Contains input files for testing (e.g., test queries)
- `data/` - Contains output files from scripts (e.g., trace results, generated data)
- `*.py` - Development scripts

## Scripts

### workflow_tracer.py

Traces LangGraph workflows and logs execution paths.

**Usage:**

```bash
# From the dev directory
python workflow_tracer.py
```

**Requirements:**

- Environment variables must be set (OPENAI_API_KEY, etc.)
- Input file: `input/test_queries.json`
- Output: `data/workflow_trace_results_YYYY-MM-DD_HH-MM-SS.json`

### visualize_workflow.py

Visualizes the LangGraph workflow structure and generates Mermaid diagrams.

**Usage:**

```bash
# From the dev directory
python visualize_workflow.py
```

### test_openai_latency.py

Tests the latency of different OpenAI models at various query lengths. Measures total response time, time to first token, and tokens per second.

**Usage:**

```bash
# From the dev directory
python test_openai_latency.py
```

**Features:**

- Tests multiple models: GPT-3.5 Turbo, GPT-4o Mini, GPT-4o
- Tests various query lengths: 50, 100, 500, 1000, 2000 characters
- Financial-related test queries
- Multiple iterations per combination for reliable averages
- Console output with real-time progress
- JSON report generation in `latency_reports/` directory

**Requirements:**

- `OPENAI_API_KEY` environment variable must be set
- `openai` package installed

**Output:**

- Console summary with performance metrics
- Detailed JSON report: `latency_reports/latency_report_YYYYMMDD_HHMMSS.json`

## Fixed Issues

- ✅ Import path issues resolved - scripts can now be run from any directory
- ✅ Organized input/output folders for better file management
- ✅ All relative imports converted to absolute imports
