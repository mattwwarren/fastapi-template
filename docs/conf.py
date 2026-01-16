"""Sphinx configuration for the FastAPI template docs."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

project = "FastAPI Template"
author = "FastAPI Template Contributors"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "furo"
html_static_path = ["_static"]

autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
