import os

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_URL = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "99999"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "1600"))


def model_for(role: str, fallback: str) -> str:
    env_key = f"OLLAMA_{role.upper()}_MODEL"
    return os.getenv(env_key, os.getenv("OLLAMA_DEFAULT_MODEL", fallback))


def run_model(model: str, prompt: str) -> str:
    selected_model = model
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": selected_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": OLLAMA_NUM_PREDICT
                }
            },
            timeout=OLLAMA_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        return (
            "LOCAL_MODEL_TIMEOUT\n\n"
            f"Ollama was reached at {OLLAMA_BASE_URL}, but the model did not finish within "
            f"{OLLAMA_TIMEOUT_SECONDS} seconds.\n"
            f"Model: {selected_model}\n"
            f"Error: {exc}\n\n"
            "Use a smaller model, increase OLLAMA_TIMEOUT_SECONDS, or run the task again after "
            "Ollama finishes its current work."
        )
    except requests.RequestException as exc:
        return (
            "LOCAL_MODEL_UNAVAILABLE\n\n"
            f"Ollama could not be reached at {OLLAMA_BASE_URL}.\n"
            f"Model: {selected_model}\n"
            f"Error: {exc}\n\n"
            "Start Ollama and install the configured model, then run this task again."
        )

    return response.json()["response"]


def ollama_health() -> dict:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "ok": True,
            "base_url": OLLAMA_BASE_URL,
            "models": [model["name"] for model in data.get("models", [])]
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "base_url": OLLAMA_BASE_URL,
            "error": str(exc)
        }


def model_preflight(required_roles: list[str] | None = None) -> dict:
    roles = required_roles or ["manager", "developer", "reviewer", "security", "testing"]
    fallbacks = {
        "manager": "qwen2.5:3b",
        "developer": "qwen2.5-coder:3b",
        "reviewer": "qwen2.5:3b",
        "security": "qwen2.5-coder:3b",
        "testing": "qwen2.5-coder:3b",
    }
    required_models = {
        role: model_for(role, fallbacks.get(role, "qwen2.5-coder:3b"))
        for role in roles
    }

    health = ollama_health()
    if not health.get("ok"):
        return {
            "ok": False,
            "code": "LOCAL_MODEL_UNAVAILABLE",
            "message": f"Ollama could not be reached at {OLLAMA_BASE_URL}.",
            "health": health,
            "required_models": required_models,
            "missing_models": sorted(set(required_models.values())),
        }

    installed = set(health.get("models", []))
    missing = sorted({model for model in required_models.values() if model not in installed})
    if missing:
        return {
            "ok": False,
            "code": "LOCAL_MODEL_MISSING",
            "message": "Ollama is running, but one or more configured models are not installed.",
            "health": health,
            "required_models": required_models,
            "missing_models": missing,
        }

    return {
        "ok": True,
        "code": "LOCAL_MODEL_READY",
        "message": "Ollama is reachable and required models are installed.",
        "health": health,
        "required_models": required_models,
        "missing_models": [],
    }
