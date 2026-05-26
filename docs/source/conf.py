"""Sphinx configuration for the network-lang documentation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# -- Project information -----------------------------------------------------

project = "network-lang"
copyright = "2026, Unified Network Syntax contributors"
author = "Unified Network Syntax contributors"
release = "0.1.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["build", "Thumbs.db", ".DS_Store"]
source_suffix = {
    ".rst": "restructuredtext",
}

autosummary_generate = True
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True



# -- Options for HTML output -------------------------------------------------

html_theme = "alabaster"
html_static_path = ["_static"]
