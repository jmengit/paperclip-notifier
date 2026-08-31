from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from .http import HTTPError, request


class PaperclipClient:
    def __init__(self, base_url: str, api_key: str, company_id: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.company_id = company_id
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        # The Paperclip instance is intentionally LAN-only HTTP in the native
        # Unraid deployment.  The explicit opt-in is scoped to this trusted
        # source client; outbound notification destinations retain SSRF checks.
        response = request("GET", self.base_url + path, headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}, timeout=self.timeout, allow_private=True)
        if not 200 <= response.status < 300:
            raise HTTPError(f"Paperclip returned HTTP {response.status}", status=response.status)
        try:
            return json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise HTTPError("Paperclip returned invalid JSON") from exc

    def health(self) -> Any:
        return self._get("/api/health")

    def company(self) -> dict[str, Any]:
        data = self._get(f"/api/companies/{quote(self.company_id, safe='')}")
        return data if isinstance(data, dict) else {}

    def activity(self, limit: int = 500) -> list[dict[str, Any]]:
        data = self._get(f"/api/companies/{quote(self.company_id, safe='')}/activity?limit={min(max(limit, 1), 500)}")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("items", "activity", "data"):
                if isinstance(data.get(key), list):
                    return [x for x in data[key] if isinstance(x, dict)]
        return []
