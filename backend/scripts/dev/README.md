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

## Fixed Issues

- ✅ Import path issues resolved - scripts can now be run from any directory
- ✅ Organized input/output folders for better file management
- ✅ All relative imports converted to absolute imports
