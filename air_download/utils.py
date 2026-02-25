"""Utility functions for output path handling and CSV writing."""

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CSV_HEADER = [
    "mrn",
    "accession_number",
    "date_time",
    "sex",
    "birthdate",
    "description",
    "image_count",
]


def build_exam_output_path(
    base_output: Path | None, exam: dict[str, Any], exam_index: int
) -> Path:
    """Generate a unique output path for each exam.

    Handles three cases:

    - ``base_output`` is a directory (or has no ``.zip`` extension): creates
      ``base_output / <accessionNumber>.zip``
    - ``base_output`` is a ``.zip`` path that doesn't exist: returns it as-is
    - ``base_output`` is a ``.zip`` path that exists: appends index to avoid
      overwriting

    Args:
        base_output: The user-provided output path. If None, defaults to
            current directory.
        exam: The exam object from the API.
        exam_index: Index of the current exam in the loop.

    Returns:
        The resolved output path for this exam.
    """
    p = base_output if base_output is not None else Path(".")
    if p.suffix.lower() != ".zip":
        # p is supposed to be a directory
        p.mkdir(parents=True, exist_ok=True)
        acc_num = exam.get("accessionNumber") or f"exam_{exam_index + 1}"
        return p / f"{acc_num}.zip"
    elif not p.exists():
        return p
    else:
        # User provided a filename; append index to avoid overwriting
        return p.with_name(f"{p.stem}_{exam_index + 1}{p.suffix}")


def write_exams_csv(
    exams: list[dict[str, Any]], output_dir: Path, mrn: str | None = None
) -> Path:
    """Write exam search results to a CSV file.

    Appends to the file if it already exists. Writes a header row only if
    the file is new. The MRN column is populated from the user-provided
    ``mrn`` argument; if not given, falls back to ``patientId`` from each
    exam object (returned by the API when searching by accession).

    Args:
        exams: List of exam dictionaries from the API.
        output_dir: Directory where ``accessions.csv`` will be written.
        mrn: Patient MRN to include in each row. If None, the ``patientId``
            field from each exam is used instead.

    Returns:
        Path to the written CSV file.
    """
    output_csv = output_dir / "accessions.csv"
    file_exists = output_csv.exists()
    logger.info("Writing accessions to %s", output_csv)

    with open(output_csv, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(_CSV_HEADER)
        for exam in exams:
            writer.writerow(
                [
                    mrn or exam.get("patientId", ""),
                    exam.get("accessionNumber", ""),
                    exam.get("dateTime", ""),
                    exam.get("sex", ""),
                    exam.get("birthdate", ""),
                    exam.get("description", ""),
                    exam.get("imageCount", ""),
                ]
            )

    logger.info("Accessions written to file.")
    return output_csv
