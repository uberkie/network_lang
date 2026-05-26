"""Reference parser for the Unified Network Syntax draft."""

from .api import OperationBuilder, build_operation, network
from .flows import (
    FlowObservation,
    FlowTargetResolution,
    flow_observations_to_attachments,
    flow_observations_to_devices,
    resolve_flow_target,
)
from .model import Operation, SourceSpan
from .parser import ParseError, parse_file, parse_text
from .reconcile import DeviceMatch, DeviceRecord, ReconciliationReport, reconcile_devices
from .result import OperationResult, ResultError
from .topology import (
    AttachmentMatch,
    AttachmentMove,
    AttachmentRecord,
    AttachmentReconciliationReport,
    DuplicateAttachment,
    TopologyPreflightReport,
    preflight_interface_operation,
    reconcile_attachments,
)
from .validation import Diagnostic, validate_operation, validate_operations

__all__ = [
    "AttachmentMatch",
    "AttachmentMove",
    "AttachmentRecord",
    "AttachmentReconciliationReport",
    "DeviceMatch",
    "DeviceRecord",
    "Diagnostic",
    "DuplicateAttachment",
    "FlowObservation",
    "FlowTargetResolution",
    "flow_observations_to_attachments",
    "flow_observations_to_devices",
    "Operation",
    "OperationBuilder",
    "OperationResult",
    "ParseError",
    "ResultError",
    "SourceSpan",
    "build_operation",
    "network",
    "parse_file",
    "parse_text",
    "preflight_interface_operation",
    "ReconciliationReport",
    "reconcile_attachments",
    "reconcile_devices",
    "resolve_flow_target",
    "TopologyPreflightReport",
    "validate_operation",
    "validate_operations",
]
