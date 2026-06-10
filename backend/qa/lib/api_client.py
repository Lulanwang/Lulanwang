"""Thin httpx wrapper that carries the bearer token + records request/response."""
from __future__ import annotations

import contextlib
import json
from typing import Any, Iterator

import httpx


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self, extra: dict | None = None) -> dict:
        h: dict[str, str] = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if extra:
            h.update(extra)
        return h

    def login(self, email: str, password: str) -> str:
        r = httpx.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=10.0,
        )
        r.raise_for_status()
        token = r.json()["token"]
        self.token = token
        return token

    def get(self, path: str, **kw) -> httpx.Response:
        return httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers(kw.pop("headers", None)),
            timeout=30.0,
            **kw,
        )

    def post(self, path: str, **kw) -> httpx.Response:
        return httpx.post(
            f"{self.base_url}{path}",
            headers=self._headers(kw.pop("headers", None)),
            timeout=30.0,
            **kw,
        )

    def patch(self, path: str, **kw) -> httpx.Response:
        return httpx.patch(
            f"{self.base_url}{path}",
            headers=self._headers(kw.pop("headers", None)),
            timeout=30.0,
            **kw,
        )

    def delete(self, path: str, **kw) -> httpx.Response:
        return httpx.delete(
            f"{self.base_url}{path}",
            headers=self._headers(kw.pop("headers", None)),
            timeout=30.0,
            **kw,
        )

    @contextlib.contextmanager
    def stream_post(self, path: str, **kw) -> Iterator[httpx.Response]:
        with httpx.stream(
            "POST",
            f"{self.base_url}{path}",
            headers=self._headers(kw.pop("headers", None)),
            timeout=60.0,
            **kw,
        ) as r:
            yield r


def excerpt(resp: httpx.Response, limit: int = 200) -> str:
    """Compact one-line summary of an HTTP response for the report."""
    s = f"{resp.status_code}"
    try:
        body = resp.json()
        if isinstance(body, list):
            s += f" · list len={len(body)}"
            if body:
                s += f" · first={json.dumps(body[0])[:120]}"
        elif isinstance(body, dict):
            keys = list(body.keys())[:6]
            s += f" · keys={keys}"
    except Exception:  # noqa: BLE001
        text = resp.text[:limit].replace("\n", " ")
        if text:
            s += f" · text={text!r}"
    return s
