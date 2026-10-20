"""OpenRouter structured generation with a deterministic template fallback.

Model output is untrusted: it is schema-validated, post-validated by the caller, and
never used for money arithmetic. Any failure falls back to the template.
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ids import new_id
from app.models import AiRun

logger = logging.getLogger("backit.ai")

T = TypeVar("T", bound=BaseModel)
Source = Literal["ai", "template"]


class AiUnavailable(Exception):
    pass


def _openrouter_call(system: str, user: str, schema: type[BaseModel], name: str) -> tuple[str, dict]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise AiUnavailable("OPENROUTER_API_KEY not configured")
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": _strict_schema(schema)},
        },
        "temperature": 0.4,
        "max_tokens": 1200,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.web_base_url,
        "X-Title": "BackIt",
    }
    resp = httpx.post(
        f"{settings.openrouter_base_url}/chat/completions",
        json=body,
        headers=headers,
        timeout=settings.ai_timeout_seconds,
    )
    if resp.status_code != 200:
        raise AiUnavailable(f"OpenRouter returned {resp.status_code}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise AiUnavailable("OpenRouter returned non-text content")
    return content, data.get("usage") or {}


def _strict_schema(schema: type[BaseModel]) -> dict:
    """JSON schema with additionalProperties=false and all properties required (strict mode)."""
    raw = schema.model_json_schema()

    def fix(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for value in node.values():
                fix(value)
        elif isinstance(node, list):
            for value in node:
                fix(value)

    fix(raw)
    return raw


def generate(
    db: Session,
    *,
    purpose: str,
    prompt_version: str,
    actor_id: str | None,
    system: str,
    user: str,
    schema: type[T],
    fallback: Callable[[], T],
    post_validate: Callable[[T], None] | None = None,
) -> tuple[T, Source, str]:
    """Return (output, source, ai_run_id). Records an ai_runs row either way."""
    settings = get_settings()
    started = time.monotonic()
    run = AiRun(
        id=new_id("air"),
        purpose=purpose,
        actor_id=actor_id,
        model=settings.openrouter_model if settings.ai_enabled else None,
        prompt_version=prompt_version,
        source="template",
        status="fallback",
        usage={},
    )
    output: T
    source: Source
    try:
        content, usage = _openrouter_call(system, user, schema, purpose)
        output = schema.model_validate(json.loads(content))
        if post_validate:
            post_validate(output)
        source = "ai"
        run.source = "ai"
        run.status = "ok"
        run.usage = usage
    except AiUnavailable as exc:
        run.error = str(exc)[:500]
        output = fallback()
        source = "template"
    except (httpx.HTTPError, KeyError, IndexError, ValueError, ValidationError) as exc:
        logger.warning("AI generation failed for %s: %s", purpose, type(exc).__name__)
        run.error = f"{type(exc).__name__}: {str(exc)[:400]}"
        run.status = "invalid_output" if isinstance(exc, ValidationError | ValueError) else "error"
        output = fallback()
        source = "template"
    run.output = output.model_dump()
    run.latency_ms = int((time.monotonic() - started) * 1000)
    db.add(run)
    db.flush()
    return output, source, run.id
