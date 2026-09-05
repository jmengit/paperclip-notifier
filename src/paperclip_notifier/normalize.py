from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
_DECISION_MARKERS = ("decision needed", "decision is needed")
_RECOMMENDATION = re.compile(r"recommendation:\s*\**([^\n\r]+?)(?:\*\*)?(?=\s*$)", re.IGNORECASE)
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
    attention_source = str(_first(row, "sourceKind", "source_kind", default=""))
    entity_type = str(_first(row, "entityType", "entity_type", default=attention_source or "unknown"))
    entity_id = _first(row, "entityId", "entity_id")
    run_id = _first(row, "runId", "run_id", default=details.get("runId", details.get("run_id")))
    body_snippet = str(_first(row, "bodySnippet", "body_snippet", default=details.get("bodySnippet", details.get("body_snippet", ""))) or "")
    decision_fields = (
        row.get("decisionNeeded"), row.get("decision_needed"),
        details.get("decisionNeeded"), details.get("decision_needed"),
    )
    decision_needed = any(value is True for value in decision_fields) or any(marker in body_snippet.lower() for marker in _DECISION_MARKERS)
    recommendation_match = _RECOMMENDATION.search(body_snippet)
    recommendation = recommendation_match.group(1).strip().rstrip("*") if recommendation_match else None
    attention_id = _first(row, "id", "attentionId", "attention_id")
    attention_dedup_key = _first(row, "dedupKey", "dedup_key")
    if entity_type.lower() in {"run", "heartbeat_run", "heartbeat_run_event", "agent_run"} and run_id:
        entity_id = run_id
    raw_subject = _first(row, "subject", default={})
    raw_related = _first(row, "relatedIssue", "related_issue", default={})
    if not isinstance(raw_subject, dict):
        raw_subject = {}
    if not isinstance(raw_related, dict):
        raw_related = {}
    subject = {
        "type": str(raw_subject.get("kind") or entity_type),
        "id": raw_subject.get("id") or entity_id,
        "identifier": raw_subject.get("identifier") or _first(row, "entityIdentifier", "entity_identifier", "identifier", "issueIdentifier", "issue_identifier", default=details.get("identifier")),
        "title": raw_subject.get("title") or _first(row, "entityTitle", "entity_title", "title", default=details.get("title")),
        "agent_id": _first(row, "agentId", "agent_id", default=details.get("agentId", details.get("agent_id"))),
        "run_id": run_id,
    }
    if raw_related.get("id") and not subject.get("id"):
        subject["id"] = raw_related["id"]
    if raw_related.get("identifier") and not subject.get("identifier"):
        subject["identifier"] = raw_related["identifier"]
    if raw_related.get("title") and not subject.get("title"):
        subject["title"] = raw_related["title"]
    actor = {
        "type": str(_first(row, "actorType", "actor_type", default="unknown")),
        "id": _first(row, "actorId", "actor_id"),
        "name": _first(row, "actorName", "actor_name", default=details.get("actorName")),
    }
    raw_detail = _first(row, "detail", default={})
    if not isinstance(raw_detail, dict):
        raw_detail = {}
    detail_text = str(raw_detail.get("description") or raw_detail.get("message") or "")
    why_now = str(_first(row, "whyNow", "why_now", default="") or "")
    decision_verbs = _first(row, "decisionVerbs", "decision_verbs", default=[])
    if not isinstance(decision_verbs, list):
        decision_verbs = []
    summary = str(_first(row, "summary", "message", default=" ".join(x for x in [
        why_now or detail_text or action,
        subject.get("title") or subject.get("identifier") or entity_id or "",
    ] if x)))
    if attention_source and decision_verbs:
        labels = [str(v.get("label")) for v in decision_verbs if isinstance(v, dict) and v.get("label")]
        if labels:
            summary += " Actions: " + ", ".join(labels[:5])
    if attention_source and raw_related.get("status") == "blocked":
        summary = "Blocked: " + summary
    summary = summary.strip()
    if attention_source and not summary:
        summary = "Paperclip attention item requires action"

    return {
        "schema_version": "1.0",
        "event_id": str(attention_id or attention_dedup_key or event_key(company_id, row)),
        "event_type": attention_source or action,
        "occurred_at": parse_time(_first(row, "createdAt", "created_at", "activityAt", "activity_at")),
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "company": {"id": company_id, "name": company.get("name"), "issue_prefix": company.get("issuePrefix") or company.get("issue_prefix")},
        "actor": actor,
        "subject": subject,
        "summary": summary[:1000],
        "detail": raw_detail,
        "severity": str(_first(row, "severity", default=details.get("severity", "info"))),
        "source": {"type": "paperclip_attention" if attention_source else "paperclip_activity", "activity_id": str(attention_id or attention_dedup_key or event_key(company_id, row)), "action": action},
        "metadata": {k: details[k] for k in ("reason", "status", "priority") if k in details},
        "attention": {"source_kind": attention_source, "dedup_key": attention_dedup_key} if attention_source else None,
        "paperclip_url": _first(raw_subject, "href", default=_first(raw_related, "href", default=None)),
        "decision_needed": decision_needed,
        "recommendation": recommendation,
    }
