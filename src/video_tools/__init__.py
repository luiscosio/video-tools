"""Discover the shared pipeline after a project's own adapters.

A project adds PIPELINE_PATH to its package search path. Relative imports then
bind to that project's configuration and scenario hooks even when two clients
run in the same process.
"""

from pathlib import Path

PIPELINE_PATH = str(Path(__file__).parent / "pipeline")
__path__.append(PIPELINE_PATH)
