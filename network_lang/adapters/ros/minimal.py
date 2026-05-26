from __future__ import annotations

import base64
import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


@dataclass(frozen=True)
class HTTPError(Exception):
    status_code: int
    body: str

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.body}"


class Response:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(self.status_code, self.text)


class Session:
    def __init__(
        self,
        username: str,
        password: str,
        verify_tls: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> Response:
        if params:
            query = parse.urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"
        return self._request("GET", url, verify=verify)

    def put(self, url: str, json: dict[str, Any] | None = None) -> Response:
        return self._request("PUT", url, json_body=json)

    def patch(self, url: str, json: dict[str, Any] | None = None) -> Response:
        return self._request("PATCH", url, json_body=json)

    def post(self, url: str, json: dict[str, Any] | None = None) -> Response:
        return self._request("POST", url, json_body=json)

    def delete(self, url: str) -> Response:
        return self._request("DELETE", url)

    def _request(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> Response:
        body = None
        headers = {
            "Authorization": _basic_auth(self.username, self.password),
            "Accept": "application/json",
        }
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=body, headers=headers, method=method)
        context = _ssl_context(self.verify_tls if verify is None else verify)
        try:
            with request.urlopen(req, timeout=self.timeout, context=context) as response:
                text = response.read().decode("utf-8")
                return Response(response.status, text)
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return Response(exc.code, text)


class Ros:
    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        session: Session | None = None,
        secure: bool = False,
        filename: str = "rest",
        url: str = "",
        timeout: float = 10.0,
    ) -> None:
        if not server.endswith("/"):
            server = f"{server}/"
        self.server = server
        self.username = username
        self.password = ""
        self.secure = secure
        self.filename = filename
        self.url = url or f"{server}{filename}"
        self.session = session or Session(username, password, secure, timeout)


def _basic_auth(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("utf-8")
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


def _ssl_context(verify_tls: bool) -> ssl.SSLContext | None:
    if verify_tls:
        return None
    return ssl._create_unverified_context()
