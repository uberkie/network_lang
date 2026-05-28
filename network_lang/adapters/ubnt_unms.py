from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin

import requests

from ..model import Operation
from ..result import OperationResult, ResultError


UNMS_ADAPTER = {
    "vendor": "ubnt",
    "platform": "unms",
    "transport": "rest",
    "name": "unms-rest",
}

HEADER_AUTH_TOKEN = "x-auth-token"


class UNMSTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class UNMSEndpoints:
    base_url: str
    api_version: str = "v2.1"

    @classmethod
    def from_url(cls, url: str, api_version: str = "v2.1") -> "UNMSEndpoints":
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
        if not isinstance(api_version, str) or not api_version.strip():
            raise ValueError("api_version must be a non-empty string")

        normalized = url.strip().replace("crm/", "nms/")
        return cls(normalized.rstrip("/"), api_version.strip().strip("/"))

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/{self.api_version}/"

    def resource_url(self, path: str) -> str:
        clean_path = path.strip().lstrip("/")
        if not clean_path:
            return self.api_url
        return urljoin(self.api_url, clean_path)


class UNMSRestTransport:
    """Execute UNMS/UISP controller API calls with token authentication."""

    def __init__(
        self,
        endpoints: UNMSEndpoints | str,
        token: str,
        *,
        session: Any | None = None,
        verify: bool = True,
        timeout: float = 30,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token must be a non-empty string")

        self.endpoints = endpoints
        if not isinstance(endpoints, UNMSEndpoints):
            self.endpoints = UNMSEndpoints.from_url(endpoints)
        self.token = token
        self.session = session or requests.Session()
        self.verify = verify
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        response = self.session.request(
            method.upper(),
            self.endpoints.resource_url(path),
            params=params,
            json=body,
            headers={HEADER_AUTH_TOKEN: self.token},
            verify=self.verify,
            timeout=self.timeout,
        )

        if hasattr(response, "raise_for_status"):
            response.raise_for_status()

        text = getattr(response, "text", "")
        if not text:
            return None
        return json.loads(text)


class UNMSExecutor:
    def __init__(self, transport: UNMSTransport) -> None:
        self.transport = transport

    def execute(self, operation: Operation) -> OperationResult:
        plan = plan_unms_operation(operation)
        return self.execute_plan(operation, plan)

    def execute_plan(
        self,
        operation: Operation,
        plan: "UNMSPlan",
    ) -> OperationResult:
        if not plan.supported:
            return _result_error(
                operation,
                plan.capability,
                "UNSUPPORTED_OPERATION",
                plan.warnings[0] if plan.warnings else "operation is unsupported",
                warnings=plan.warnings,
            )

        outputs: list[Any] = []
        try:
            for step in plan.steps:
                outputs.append(
                    self.transport.request(
                        step.method,
                        step.path,
                        params=step.params,
                        body=step.body,
                    )
                )
        except Exception as error:
            return _result_error(
                operation,
                plan.capability,
                "ADAPTER_ERROR",
                str(error),
                warnings=plan.warnings,
            )

        data = outputs[0] if len(outputs) == 1 else outputs
        return OperationResult(
            ok=True,
            operation=operation.name,
            target=operation.target,
            capability=plan.capability,
            adapter=dict(UNMS_ADAPTER),
            data=data,
            warnings=plan.warnings,
        )


def execute_unms_operation(
    operation: Operation,
    transport: UNMSTransport,
) -> OperationResult:
    return UNMSExecutor(transport).execute(operation)


@dataclass(frozen=True)
class UNMSPlanStep:
    name: str
    method: str
    path: str
    params: dict[str, Any] | None = None
    body: dict[str, Any] | None = None


@dataclass(frozen=True)
class UNMSPlan:
    operation: str
    capability: str
    steps: tuple[UNMSPlanStep, ...]
    warnings: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.capability == "supported"


def plan_unms_operation(operation: Operation) -> UNMSPlan:
    """Translate a controller operation into UNMS/UISP API calls."""

    endpoint = _controller_endpoint(operation)
    if not endpoint:
        return _unsupported(
            operation,
            "operation is not mapped for UNMS/UISP controller API",
        )

    if operation.action == "list":
        return _get(operation, endpoint, _filters(operation))
    if operation.action == "get":
        resource_id = _resource_id(operation)
        if resource_id:
            return _get(operation, f"{endpoint}/{resource_id}")
        filters = _filters(operation)
        if filters:
            return _get(operation, endpoint, filters)
        return _unsupported(operation, "get requires id or match params")
    if operation.action == "create":
        body = _body(operation)
        if not body:
            return _unsupported(operation, "create requires data params")
        return _write(operation, "POST", endpoint, body)
    if operation.action == "update":
        resource_id = _resource_id(operation)
        body = _body(operation)
        if not resource_id:
            return _unsupported(operation, "update requires id params")
        if not body:
            return _unsupported(operation, "update requires data params")
        return _write(operation, "PATCH", f"{endpoint}/{resource_id}", body)
    if operation.action == "delete":
        resource_id = _resource_id(operation)
        if not resource_id:
            return _unsupported(operation, "delete requires id params")
        return UNMSPlan(
            operation=operation.name,
            capability="supported",
            steps=(
                UNMSPlanStep(
                    operation.action,
                    "DELETE",
                    f"{endpoint}/{resource_id}",
                ),
            ),
            warnings=("delete is destructive on the controller",),
        )

    return _unsupported(
        operation,
        f"controller endpoint does not support action {operation.action!r}",
    )


def _controller_endpoint(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None

    resource_path = operation.resource_path
    if not resource_path:
        return None

    if resource_path[0] == "controller":
        resource_path = resource_path[1:]
    elif resource_path[0] == "unms":
        resource_path = resource_path[1:]
    else:
        return None

    if not resource_path:
        endpoint = operation.params.get("endpoint")
        if isinstance(endpoint, str) and endpoint.strip():
            return _normalize_path(endpoint)
        return None

    return "/" + "/".join(_path_segment(segment) for segment in resource_path)


def _get(
    operation: Operation,
    path: str,
    params: dict[str, Any] | None = None,
) -> UNMSPlan:
    return UNMSPlan(
        operation=operation.name,
        capability="supported",
        steps=(UNMSPlanStep(operation.action, "GET", path, params=params),),
    )


def _write(
    operation: Operation,
    method: str,
    path: str,
    body: dict[str, Any],
) -> UNMSPlan:
    return UNMSPlan(
        operation=operation.name,
        capability="supported",
        steps=(UNMSPlanStep(operation.action, method, path, body=body),),
    )


def _filters(operation: Operation) -> dict[str, Any]:
    match = operation.params.get("match", {})
    if isinstance(match, dict):
        return _translate_keys(match)
    query = operation.params.get("query", {})
    if isinstance(query, dict):
        return _translate_keys(query)
    return {}


def _body(operation: Operation) -> dict[str, Any]:
    data = operation.params.get("data", {})
    if isinstance(data, dict):
        return _translate_keys(data)
    return {}


def _resource_id(operation: Operation) -> str | None:
    for key in ("id", "device_id", "site_id", "client_id"):
        value = operation.params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _path_segment(value: str) -> str:
    return value.replace("_", "-")


def _normalize_path(path: str) -> str:
    return "/" + path.strip().strip("/")


def _translate_keys(values: dict[str, Any]) -> dict[str, Any]:
    return {key.replace("_", "-"): value for key, value in values.items()}


def _unsupported(operation: Operation, reason: str) -> UNMSPlan:
    return UNMSPlan(
        operation=operation.name,
        capability="unsupported",
        steps=(),
        warnings=(reason,),
    )


def _result_error(
    operation: Operation,
    capability: str,
    code: str,
    message: str,
    warnings: tuple[str, ...] = (),
) -> OperationResult:
    return OperationResult(
        ok=False,
        operation=operation.name,
        target=operation.target,
        capability=capability,
        adapter=dict(UNMS_ADAPTER),
        warnings=warnings,
        error=ResultError(code, message),
    )
