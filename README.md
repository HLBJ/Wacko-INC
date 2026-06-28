# Wacko Inc OS

A local-first control panel for running a small AI software company from one machine.

## What works in this v1

- Submit one CEO goal to the Manager Agent.
- Automatically create a project and delegated specialist tasks.
- Automatically start specialist agents after planning.
- Seed new projects from stack-aware templates: Auto, FastAPI, Vue, FastAPI + Vue, or .NET API.
- Ask agents to study and update an existing project folder.
- Create projects.
- Create tasks and assign them to specialist agents.
- Run agent tasks through the local Ollama-backed agent pipeline.
- Write generated project files to `C:/Project/<Project_Name>` by default.
- Run stack-aware build/test checks and capture logs.
- Create fix tasks automatically when build/test checks fail.
- Initialize Git, inspect diffs, and commit generated project changes.
- Approve and commit change sets, or reject and revert uncommitted project changes.
- Run agent tasks on isolated `wacko/task-*` Git branches.
- Track background agent/build work as jobs.
- Run long jobs in separate worker processes.
- Cancel pending/running jobs and terminate active worker processes when possible.
- Retry completed, failed, or cancelled jobs.
- Use a Project Command Center with Autopilot, Auto Next Step, Full Cycle, Build Until Pass, health checks, and release readiness checks.
- Show each agent department's project workload in the command center.
- Check Ollama/model readiness before starting workflows that need AI generation.
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

Ollama is only required when the Manager or specialist agents need to think or generate code. You can keep Ollama stopped while browsing the dashboard, reviewing files, running deterministic quality/security checks, and checking existing build logs.

When you want agents to run, start Ollama and make sure these models are available:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
```

If those models are too slow on your machine, use smaller models:

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5-coder:3b
```

Or use the local setup helper:

```powershell
.\scripts\setup-models.ps1 -Fast
```

Then create a `.env` file from `.env.example` and set:

```text
OLLAMA_MANAGER_MODEL=qwen2.5:3b
OLLAMA_REVIEWER_MODEL=qwen2.5:3b
OLLAMA_DEVELOPER_MODEL=qwen2.5-coder:3b
OLLAMA_SECURITY_MODEL=qwen2.5-coder:3b
OLLAMA_TESTING_MODEL=qwen2.5-coder:3b
OLLAMA_TIMEOUT_SECONDS=99999
OUTPUT_BASE_DIR=C:/Project
```

Start the app:

```powershell
.\scripts\start-company.ps1 -Port 8199
```

Open:

```text
http://127.0.0.1:8199
```

To also try starting Ollama from the launcher:

```powershell
.\scripts\start-company.ps1 -Port 8199 -StartOllama
```

From Git Bash, use the shell wrapper instead of running the PowerShell script directly:

```bash
./scripts/start-company.sh -Port 8199
```

Stop the app:

```powershell
.\scripts\stop-dev.ps1 -Port 8199
```

Run local checks:

```powershell
.\scripts\check.ps1
```

For mobile access on your local network, bind to all interfaces:

```powershell
.\scripts\start-company.ps1 -HostName 0.0.0.0 -Port 8199
```

Then open `http://YOUR_PC_IP:8199` from your phone while connected to the same network.

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

- Per-agent tool permissions.
- Persistent worker queue with concurrency limits.
- Rich build/test log review and retry controls.
- Support inbox ingestion.
- Marketing research connectors.
- Desktop packaging with Tauri or Electron.
