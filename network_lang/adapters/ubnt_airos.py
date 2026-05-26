from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..model import Operation


@dataclass(frozen=True)
class AirOSEndpoints:
    base_url: str

    @classmethod
    def from_host(cls, host: str, scheme: str = "https") -> "AirOSEndpoints":
        if not host.strip():
            raise ValueError("host must be a non-empty string")
        if scheme not in {"http", "https"}:
            raise ValueError("scheme must be 'http' or 'https'")
        clean_host = host.strip().strip("/")
        return cls(f"{scheme}://{clean_host}")

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/api/auth"

    @property
    def status_cgi_url(self) -> str:
        return f"{self.base_url}/status.cgi"

    @property
    def reboot_cgi_url(self) -> str:
        return f"{self.base_url}/reboot.cgi"

    @property
    def v6_xm_login_url(self) -> str:
        return f"{self.base_url}/login.cgi"

    @property
    def v6_form_url(self) -> str:
        return "/index.cgi"

    @property
    def stakick_cgi_url(self) -> str:
        return f"{self.base_url}/stakick.cgi"

    @property
    def provmode_url(self) -> str:
        return f"{self.base_url}/api/provmode"

    @property
    def warnings_url(self) -> str:
        return f"{self.base_url}/api/warnings"

    @property
    def update_check_url(self) -> str:
        return f"{self.base_url}/api/fw/update-check"

    @property
    def download_url(self) -> str:
        return f"{self.base_url}/api/fw/download"

    @property
    def download_progress_url(self) -> str:
        return f"{self.base_url}/api/fw/download-progress"

    @property
    def install_url(self) -> str:
        return f"{self.base_url}/fwflash.cgi"

    @property
    def login_urls(self) -> tuple[str, str]:
        return (self.login_url, self.v6_xm_login_url)


@dataclass(frozen=True)
class AirOSPlanStep:
    name: str
    method: str
    url: str
    params: dict[str, Any] | None = None
    body: dict[str, Any] | None = None


@dataclass(frozen=True)
class AirOSPlan:
    operation: str
    capability: str
    steps: tuple[AirOSPlanStep, ...]
    warnings: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.capability in {"supported", "supported_via_fallback"}


def plan_airos_operation(
    operation: Operation,
    endpoints: AirOSEndpoints,
    firmware_major: int | None = None,
) -> AirOSPlan:
    """Translate a vendor-neutral operation into an airOS endpoint plan.

    This is intentionally not an executor. It lets the adapter state what it
    would call before auth/session handling, retries, and normalization exist.

    Args:
        operation:
        endpoints:
        firmware_major:
    """

    if operation.name in {
        "network.system.identity.get",
        "network.system.status.get",
        "network.wireless.clients.list",
    }:
        return _status_plan(operation, endpoints, firmware_major)

    if operation.name == "network.system.warnings.get":
        return _v8_get_plan(operation, endpoints, endpoints.warnings_url)

    if operation.name == "network.system.reboot.run":
        return _v8_or_legacy_post_plan(
            operation,
            endpoints,
            endpoints.reboot_cgi_url,
            warning="reboot interrupts service and requires confirmation",
        )

    if operation.name == "network.wireless.clients.delete":
        mac = _match_value(operation, "mac")
        if not isinstance(mac, str) or not mac.strip():
            return _unsupported(operation, "wireless client delete requires match.mac")
        return _v8_post_plan(
            operation,
            endpoints,
            endpoints.stakick_cgi_url,
            body={"sta": mac},
            warning="station kick disconnects an active client",
        )

    if operation.name == "network.system.provisioning.update":
        enabled = _data_value(operation, "enabled")
        if not isinstance(enabled, bool):
            return _unsupported(
                operation,
                "provisioning mode update requires data.enabled boolean",
            )
        return _v8_post_plan(
            operation,
            endpoints,
            endpoints.provmode_url,
            body={"enabled": enabled},
        )

    if operation.name == "network.firmware.update.get":
        force = _param_map(operation, "options").get("force", False)
        return _v8_get_plan(
            operation,
            endpoints,
            endpoints.update_check_url,
            params={"force": force},
        )

    if operation.name == "network.firmware.download.run":
        return _v8_post_plan(operation, endpoints, endpoints.download_url)

    if operation.name == "network.firmware.download_progress.get":
        return _v8_get_plan(operation, endpoints, endpoints.download_progress_url)

    if operation.name == "network.firmware.install.run":
        return _v8_post_plan(
            operation,
            endpoints,
            endpoints.install_url,
            warning="firmware install interrupts service and requires confirmation",
        )

    return _unsupported(operation, "operation is not mapped for airOS")


def _status_plan(
    operation: Operation,
    endpoints: AirOSEndpoints,
    firmware_major: int | None,
) -> AirOSPlan:
    """

    Args:
        operation:
        endpoints:
        firmware_major:

    Returns:

    """
    warnings = ()
    capability = "supported"
    if firmware_major == 6:
        capability = "supported_via_fallback"
        warnings = ("airOS 6 status uses legacy login flow",)
    return AirOSPlan(
        operation=operation.name,
        capability=capability,
        steps=(
            AirOSPlanStep("login_v8", "POST", endpoints.login_url),
            AirOSPlanStep("login_v6_fallback", "POST", endpoints.v6_xm_login_url),
            AirOSPlanStep("status", "GET", endpoints.status_cgi_url),
        ),
        warnings=warnings,
    )


def _v8_get_plan(
    operation: Operation,
    endpoints: AirOSEndpoints,
    url: str,
    params: dict[str, Any] | None = None,
) -> AirOSPlan:
    """

    Args:
        operation:
        endpoints:
        url:
        params:

    Returns:

    """
    return AirOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(
            AirOSPlanStep("login_v8", "POST", endpoints.login_url),
            AirOSPlanStep(operation.action, "GET", url, params=params),
            AirOSPlanStep("logout", "POST", f"{endpoints.base_url}/logout.cgi"),
        ),
    )


def _v8_post_plan(
    operation: Operation,
    endpoints: AirOSEndpoints,
    url: str,
    body: dict[str, Any] | None = None,
    warning: str | None = None,
) -> AirOSPlan:
    """

    Args:
        operation:
        endpoints:
        url:
        body:
        warning:

    Returns:

    """
    warnings = (warning,) if warning else ()
    return AirOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(
            AirOSPlanStep("login_v8", "POST", endpoints.login_url),
            AirOSPlanStep(operation.action, "POST", url, body=body),
            AirOSPlanStep("logout", "POST", f"{endpoints.base_url}/logout.cgi"),
        ),
        warnings=warnings,
    )


def _v8_or_legacy_post_plan(
    operation: Operation,
    endpoints: AirOSEndpoints,
    url: str,
    warning: str | None = None,
) -> AirOSPlan:
    """

    Args:
        operation:
        endpoints:
        url:
        warning:

    Returns:

    """
    warnings = (warning,) if warning else ()
    return AirOSPlan(
        operation=operation.name,
        capability="supported_via_fallback",
        steps=(
            AirOSPlanStep("login_v8", "POST", endpoints.login_url),
            AirOSPlanStep("login_v6_fallback", "POST", endpoints.v6_xm_login_url),
            AirOSPlanStep(operation.action, "POST", url),
        ),
        warnings=warnings,
    )


def _unsupported(operation: Operation, reason: str) -> AirOSPlan:
    """

    Args:
        operation:
        reason:

    Returns:

    """
    return AirOSPlan(
        operation=operation.name,
        capability="unsupported",
        steps=(),
        warnings=(reason,),
    )


def _match_value(operation: Operation, key: str) -> Any:
    return _param_map(operation, "match").get(key)


def _data_value(operation: Operation, key: str) -> Any:
    return _param_map(operation, "data").get(key)


def _param_map(operation: Operation, key: str) -> dict[str, Any]:
    value = operation.params.get(key, {})
    if isinstance(value, dict):
        return value
    return {}
