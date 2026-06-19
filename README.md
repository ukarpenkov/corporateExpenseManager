# Ambient Expense Agent

A conversational corporate expense approval agent built with Google Agent Development Kit (ADK) 2.0. Users submit expenses through a chat interface — the agent collects required fields via natural conversation, runs security screening, and routes approvals automatically or escalates to managers for high-value items.

## Features

- **Conversational Expense Collection**: Users describe expenses in natural language; the agent extracts and validates fields interactively.
- **Automatic Approval**: Expenses under $100 are approved instantly.
- **Human-in-the-Loop**: High-value expenses ($100+) are escalated to managers for approval via the dashboard.
- **PII Scrubbing**: Social Security numbers and credit card numbers are redacted before reaching the model or logs.
- **Prompt Injection Defense**: Malicious instructions embedded in expense descriptions are detected and rejected.
- **Chat Interface**: Built-in chat widget in the manager dashboard for direct agent interaction.
- **Manager Dashboard**: Web UI to view pending approvals and take action.

## Project Structure

```
expense_agent/
  agent.py              — Conversational agent: tools, security screening, approval logic
  config.py             — Configuration (threshold, model)
  fast_api_app.py       — FastAPI entry point for ADK
  agent_runtime_app.py  — Agent Runtime entry point for Google Cloud deployment
  __init__.py
submission_frontend/
  main.py               — Manager dashboard with chat UI (FastAPI)
  Dockerfile            — Docker container for frontend deployment
  requirements.txt      — Frontend dependencies
Makefile                — Build/run targets
pyproject.toml          — Project metadata and dependencies
.env                    — API key configuration (not committed)
```

## Agent Tools

| Tool | Description |
|------|-------------|
| `submit_expense` | Submits an expense after security screening. Auto-approves if below threshold, otherwise returns `submitted_for_approval`. |
| `request_approval` | Requests manager approval for high-value expenses. Returns pending status. |

## Prerequisites

- Python 3.11+
- `uv` (package manager)
- DeepSeek API key (or another LiteLLM-compatible provider)

## Setup

1. Install dependencies:
   ```bash
   make install
   ```

2. Configure your API key in `.env`:
   ```
   DEEPSEEK_API_KEY=your-api-key-here
   ```

## Usage

### Interactive Playground (ADK Dev UI)

```bash
make playground
```

Opens the ADK Playground at `http://localhost:8080/dev-ui/` where you can test the agent interactively.

### Agent Runtime Server (FastAPI)

```bash
make serve
```

Starts the FastAPI server on port 8080.

### Manager Dashboard

```bash
cd submission_frontend
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Opens the dashboard at `http://localhost:8000` with:
- Pending expense approvals (auto-refreshes every 15s)
- Chat widget for direct agent interaction

### Docker Deployment (Frontend)

```bash
cd submission_frontend
docker build -t expense-dashboard .
docker run -p 8000:8080 -e AGENT_URL=http://your-agent-url:8080 expense-dashboard
```

## How It Works

1. **Collect** — User describes an expense in chat. The agent extracts amount, submitter, category, description, and date — asking for missing fields one at a time.
2. **Security Screen** — When all fields are collected, `submit_expense` scrubs PII and checks for prompt injection. Malicious payloads are rejected immediately.
3. **Route by Amount** — Under $100 → auto-approved. $100+ → submitted for manager approval.
4. **Manager Decision** — High-value expenses appear in the dashboard. Managers approve or reject via the UI.
5. **Confirm** — The agent confirms the decision back to the user.

## Configuration

All configuration lives in `expense_agent/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `THRESHOLD` | `100` | Dollar amount below which expenses are auto-approved |
| `MODEL` | `deepseek/deepseek-chat` | LLM used for the conversational agent (via LiteLLM) |

## Evaluation

```bash
make generate-traces   # run test scenarios through the agent
make grade             # score traces and print summary table
make eval              # both in sequence
```

Test scenarios: auto-approve, high-value review, PII in description, prompt injection, exact $100 threshold.

Results are written to `artifacts/grade_results/grade_report.json`.
