from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urljoin


@dataclass(frozen=True)
class LinkContext:
    public_url: str
    issue_prefix: str

    def link(self, subject_type: str, subject: dict) -> tuple[str, str]:
        """Build a link only from normalized, API-derived fields."""
        base = self.public_url.rstrip("/") + "/"
        kind = subject_type.lower().replace("-", "_")
        ident = str(subject.get("identifier") or subject.get("id") or "").strip()
        if not ident:
            return urljoin(base, f"{quote(self.issue_prefix, safe='')}/activity"), "activity"
        prefix = quote(self.issue_prefix, safe="")
        ident_q = quote(ident, safe="")
        if kind in {"issue", "inbox", "inbox_item"}:
            return urljoin(base, f"{prefix}/issues/{ident_q}"), "issue"
        if kind in {"approval", "approval_request"}:
            return urljoin(base, f"{prefix}/approvals/{ident_q}"), "approval"
        if kind in {"agent", "agent_profile"}:
            return urljoin(base, f"{prefix}/agents/{ident_q}"), "agent"
        if kind == "project":
            return urljoin(base, f"{prefix}/projects/{ident_q}"), "project"
        if kind == "goal":
            return urljoin(base, f"{prefix}/goals/{ident_q}"), "goal"
        if kind in {"routine", "routine_execution"}:
            return urljoin(base, f"{prefix}/routines/{ident_q}"), "routine"
        if kind in {"run", "failed_run", "agent_run"}:
            agent_id = str(subject.get("agent_id") or subject.get("agentId") or "").strip()
            if agent_id:
                return urljoin(base, f"{prefix}/agents/{quote(agent_id, safe='')}/runs/{ident_q}"), "run"
        return urljoin(base, f"{prefix}/activity"), "activity"
