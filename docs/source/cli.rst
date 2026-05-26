CLI
===

The ``uns`` command is a thin wrapper around the parser and validator. It is
useful for local checks, examples, and CI jobs that only need to inspect
operation files.

Install
-------

Install the package in editable mode:

.. code-block:: sh

   python3 -m pip install -e .

This exposes the ``uns`` command from ``network_lang.cli:main``.

Validate
--------

.. code-block:: sh

   uns validate examples/operations.uns

Successful validation prints:

.. code-block:: text

   OK examples/operations.uns (10 operations)

Validation errors are printed with source labels and exit status ``1``.

Parse
-----

.. code-block:: sh

   uns parse examples/operations.uns

This prints parsed operations as JSON using ``Operation.to_dict()``.

Default Command
---------------

If the first argument is a file path rather than a command, ``uns`` treats it
as a validation request:

.. code-block:: sh

   uns examples/operations.uns

Module Form
-----------

The package can also be run as a module:

.. code-block:: sh

   python3 -m network_lang validate examples/operations.uns
   python3 -m network_lang parse examples/operations.uns
