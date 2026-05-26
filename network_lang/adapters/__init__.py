"""Adapter planning helpers for network_lang."""

from .mikrotik_routeros import (
    RouterOSPlan,
    RouterOSPlanStep,
    plan_routeros_operation,
)
from .ubnt_airos import (
    AirOSEndpoints,
    AirOSPlan,
    AirOSPlanStep,
    plan_airos_operation,
)

__all__ = [
    "AirOSEndpoints",
    "AirOSPlan",
    "AirOSPlanStep",
    "RouterOSPlan",
    "RouterOSPlanStep",
    "plan_airos_operation",
    "plan_routeros_operation",
]
