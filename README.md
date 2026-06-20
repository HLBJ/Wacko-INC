# Wacko Inc OS

A local-first control panel for running a small AI software company from one machine.

## What works in this v1

- Submit one CEO goal to the Manager Agent.
- Automatically create a project and delegated specialist tasks.
- Automatically start specialist agents after planning.
- Create projects.
- Create tasks and assign them to specialist agents.
- Run agent tasks through the local Ollama-backed agent pipeline.
- Track agent runs and outputs.
- Require CEO approval before outputs are treated as done.
- Approve or reject completed work from the dashboard.

## Agent workforce

- Manager Agent
- Frontend Agent
- Backend Agent
- Database Agent
- Security Agent
- Testing Agent
- Marketing Agent
- Support Agent

## Run locally

Install Python 3.12 or newer, then install dependencies:

```powershell
pip install -r requirements.txt
```

Start Ollama and make sure these models are available:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
```

If those models are too slow on your machine, use smaller models:

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5-coder:3b
```

Then create a `.env` file from `.env.example` and set:

```text
OLLAMA_MANAGER_MODEL=qwen2.5:3b
OLLAMA_REVIEWER_MODEL=qwen2.5:3b
OLLAMA_DEVELOPER_MODEL=qwen2.5-coder:3b
OLLAMA_TIMEOUT_SECONDS=99999
```

Start the app:

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

If Windows blocks port 8000, use a higher port:

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8127 --reload
```

For mobile access on your local network, bind to all interfaces:

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Then open `http://YOUR_PC_IP:8000` from your phone while connected to the same network.

## Safety model

This project is designed around approval gates. Agents can draft work, plans, reviews, emails, and marketing copy, but high-impact actions should remain CEO-approved:

- Deployments
- External emails
- Publishing posts or ads
- Purchases
- Data deletion
- Authentication/security changes
- Access to private customer data

## Next build targets

- Background queue for long-running agent jobs.
- Per-agent tool permissions.
- Git workspace integration for real code changes.
- Test runner integration.
- Support inbox ingestion.
- Marketing research connectors.
- Desktop packaging with Tauri or Electron.
