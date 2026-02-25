"""Tests for air_download.utils."""

import csv
from pathlib import Path

import pytest

from air_download.utils import build_exam_output_path, write_exams_csv


class TestBuildExamOutputPath:
    """Tests for build_exam_output_path."""

    def test_none_output_uses_current_dir(self):
        exam = {"accessionNumber": "12345"}
        result = build_exam_output_path(None, exam, 0)
        assert result == Path(".") / "12345.zip"

    def test_directory_path_creates_zip(self, tmp_path):
        exam = {"accessionNumber": "12345"}
        result = build_exam_output_path(tmp_path, exam, 0)
        assert result == tmp_path / "12345.zip"

    def test_directory_path_creates_dir(self, tmp_path):
        new_dir = tmp_path / "output"
        exam = {"accessionNumber": "12345"}
        result = build_exam_output_path(new_dir, exam, 0)
        assert new_dir.exists()
        assert result == new_dir / "12345.zip"

    def test_missing_accession_uses_index(self, tmp_path):
        exam = {}
        result = build_exam_output_path(tmp_path, exam, 2)
        assert result == tmp_path / "exam_3.zip"

    def test_zip_path_not_existing(self, tmp_path):
        zip_path = tmp_path / "my_download.zip"
        exam = {"accessionNumber": "12345"}
        result = build_exam_output_path(zip_path, exam, 0)
        assert result == zip_path

    def test_zip_path_existing_appends_index(self, tmp_path):
        zip_path = tmp_path / "my_download.zip"
        zip_path.touch()
        exam = {"accessionNumber": "12345"}
        result = build_exam_output_path(zip_path, exam, 0)
        assert result == tmp_path / "my_download_1.zip"

    def test_zip_path_existing_multiple_indices(self, tmp_path):
        zip_path = tmp_path / "my_download.zip"
        zip_path.touch()
        exam = {"accessionNumber": "12345"}
        r1 = build_exam_output_path(zip_path, exam, 0)
        r2 = build_exam_output_path(zip_path, exam, 1)
        assert r1 == tmp_path / "my_download_1.zip"
        assert r2 == tmp_path / "my_download_2.zip"


class TestWriteExamsCsv:
    """Tests for write_exams_csv."""

    def test_creates_csv_with_header(self, tmp_path):
        exams = [
            {
                "accessionNumber": "111",
                "dateTime": "2024-01-01",
                "sex": "M",
                "birthdate": "1990-01-01",
                "description": "BRAIN MRI",
                "imageCount": 100,
            }
        ]
        result = write_exams_csv(exams, tmp_path, mrn="MRN001")
        assert result.exists()

        with open(result) as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == [
            "mrn",
            "accession_number",
            "date_time",
            "sex",
            "birthdate",
            "description",
            "image_count",
        ]
        assert rows[1] == [
            "MRN001",
            "111",
            "2024-01-01",
            "M",
            "1990-01-01",
            "BRAIN MRI",
            "100",
        ]

    def test_appends_without_duplicate_header(self, tmp_path):
        exams = [{"accessionNumber": "111", "dateTime": "", "sex": "", "birthdate": "", "description": "", "imageCount": 0}]
        write_exams_csv(exams, tmp_path, mrn="MRN001")
        write_exams_csv(exams, tmp_path, mrn="MRN002")

        with open(tmp_path / "accessions.csv") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # One header + two data rows
        assert len(rows) == 3
        assert rows[0][0] == "mrn"
        assert rows[1][0] == "MRN001"
        assert rows[2][0] == "MRN002"

    def test_handles_commas_in_description(self, tmp_path):
        exams = [
            {
                "accessionNumber": "222",
                "dateTime": "",
                "sex": "",
                "birthdate": "",
                "description": "BRAIN, WITH CONTRAST, AXIAL",
                "imageCount": 50,
            }
        ]
        result = write_exams_csv(exams, tmp_path)

        with open(result) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # csv module should properly quote the description
        assert rows[1][5] == "BRAIN, WITH CONTRAST, AXIAL"
