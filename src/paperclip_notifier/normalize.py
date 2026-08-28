from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _first(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return default


def parse_time(value: Any) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(value)
    return text.replace("+00:00", "Z") if text.endswith("+00:00") else text


def event_key(company_id: str, row: dict[str, Any]) -> str:
    source_id = _first(row, "id", "activityId", "activity_id")
    if source_id:
        return str(source_id)
    stable = {
        "company_id": company_id,
        "created_at": parse_time(_first(row, "createdAt", "created_at")),
        "action": _first(row, "action", "eventType", "event_type", default=""),
        "entity_type": _first(row, "entityType", "entity_type", default=""),
        "entity_id": _first(row, "entityId", "entity_id", default=""),
        "details": _first(row, "details", default={}),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalize(company_id: str, company: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    details = _first(row, "details", default={}) or {}
    if not isinstance(details, dict):
        details = {}
    action = str(_first(row, "action", "eventType", "event_type", default="unknown"))
    entity_type = str(_first(row, "entityType", "entity_type", default="unknown"))
    entity_id = _first(row, "entityId", "entity_id")
    run_id = _first(row, "runId", "run_id", default=details.get("runId", details.get("run_id")))
    if entity_type.lower() in {"run", "heartbeat_run", "heartbeat_run_event", "agent_run"} and run_id:
        entity_id = run_id
    subject = {
        "type": entity_type,
        "id": entity_id,
        "identifier": _first(row, "entityIdentifier", "entity_identifier", "identifier", "issueIdentifier", "issue_identifier", default=details.get("identifier")),
        "title": _first(row, "entityTitle", "entity_title", "title", default=details.get("title")),
        "agent_id": _first(row, "agentId", "agent_id", default=details.get("agentId", details.get("agent_id"))),
        "run_id": run_id,
    }
    actor = {
        "type": str(_first(row, "actorType", "actor_type", default="unknown")),
        "id": _first(row, "actorId", "actor_id"),
        "name": _first(row, "actorName", "actor_name", default=details.get("actorName")),
    }
    summary = str(_first(row, "summary", "message", default=" ".join(x for x in [action, subject.get("title") or entity_id or ""] if x)))
    return {
        "schema_version": "1.0",
        "event_id": event_key(company_id, row),
        "event_type": action,
        "occurred_at": parse_time(_first(row, "createdAt", "created_at", "activityAt", "activity_at")),
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "company": {"id": company_id, "name": company.get("name"), "issue_prefix": company.get("issuePrefix") or company.get("issue_prefix")},
        "actor": actor,
        "subject": subject,
        "summary": summary[:1000],
        "severity": str(_first(row, "severity", default=details.get("severity", "info"))),
        "source": {"type": "paperclip_activity", "activity_id": event_key(company_id, row), "action": action},
        "metadata": {k: details[k] for k in ("reason", "status", "priority") if k in details},
    }
