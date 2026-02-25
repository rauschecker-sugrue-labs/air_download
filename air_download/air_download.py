"""Backward-compatibility shim.

This module re-exports the public API from the new module layout.
Prefer importing from ``air_download.client``, ``air_download.cli``,
``air_download.filters``, or ``air_download.utils`` directly.
"""

# ruff: noqa: F401
from air_download.cli import cli, main, parse_args
from air_download.client import AIRClient
from air_download.filters import apply_inclusion_filter
from air_download.utils import build_exam_output_path, write_exams_csv
