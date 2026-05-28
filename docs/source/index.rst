network-lang
============

Unified Network Syntax is a small Python reference implementation for a
vendor-neutral network operation model. It lets operators describe intent once,
validate that intent, and then translate it to device-specific adapters such as
MikroTik RouterOS REST or Ubiquiti airOS endpoint plans.

The project is library-first. Text files and the ``uns`` CLI are convenient
ways to parse and inspect the same operation model, but the core object is
always an :class:`network_lang.Operation`.

What Works Today
----------------

* Parse ``.uns`` operation files into typed Python operations.
* Build operations from Python with fluent access or dotted names.
* Validate namespaces, operation shape, core actions, and required targets.
* Plan and execute selected MikroTik RouterOS REST operations.
* Plan and execute UNMS/UISP controller API operations with token auth.
* Plan selected Ubiquiti airOS operations without executing them.
* Normalize RouterOS observations into inventory and topology records.
* Reconcile expected devices or attachments against observed data.
* Preflight risky interface operations against live topology observations.
* Collect NetFlow v5 endpoint evidence with a lightweight Go collector.
* Generate standalone HTML graphs from adapter-normalized operational samples.


.. toctree::
   :maxdepth: 2
   :caption: User Guide

   getting-started
   operations
   inventory
   adapters
   examples
   flowcollector
   topology-preflight
   cli
   syntax-v0

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api
