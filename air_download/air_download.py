import os
import argparse
from pathlib import Path
import time
import json
import requests
from dotenv import dotenv_values
from tqdm import tqdm
from urllib.parse import urljoin
from typing import List, Dict, Any


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "url", nargs="?", help="URL for AIR API, e.g. https://air.<domain>.edu/api/"
    )
    parser.add_argument(
        "acc", nargs="?", metavar="ACCESSION", help="Accession # to download"
    )
    parser.add_argument(
        "-c",
        "--cred-path",
        help="Login credentials file. If not present,"
        " will look for AIR_USERNAME and AIR_PASSWORD"
        " environment variables.",
        default=None,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path or directory",
        type=Path,
        default=None,
    )
    parser.add_argument("-pf", "--profile", help="Anonymization Profile", default=-1)
    parser.add_argument("-pj", "--project", help="Project ID", default=-1)
    parser.add_argument(
        "-lpj",
        "--list-projects",
        action="store_true",
        help="List available project IDs",
    )
    parser.add_argument(
        "-lpf",
        "--list-profiles",
        action="store_true",
        help="List available anonymization profiles",
    )
    parser.add_argument("-mrn", "--mrn", help="Patient ID to download")
    parser.add_argument(
        "-xm",
        "--exam_modality_inclusion",
        help=(
            "Comma-separated list of exam modality inclusion patterns (case "
            "insensitive, 'or' logic) for exam . Example: 'MR,CT'"
        ),
        default=None,
    )
    parser.add_argument(
        "-xd",
        "--exam_description_inclusion",
        help=(
            "Comma-separated list of exam description inclusion patterns (case "
            "insensitive, 'or' logic) for exam . Example: 'BRAIN WITH AND WITHOUT CONTRAST'"
        ),
        default=None,
    )
    parser.add_argument(
        "-s",
        "--series_inclusion",
        help=(
            "Comma-separated list of series inclusion patterns (case insensitive, 'or' "
            "logic). Example for T1 type series: 't1,spgr,bravo,mpr'"
        ),
        default=None,
    )
    parser.add_argument(
        "--only-return-accessions",
        action="store_true",
        help=(
            "Only return the accessions found for the provided search parameters. "
            "Also writes them (appending) to ``output``/accessions.csv."
        ),
    )
    arguments = parser.parse_args()

    if not (arguments.list_projects or arguments.list_profiles):
        # At least one of 'acc' or 'mrn' must be provided
        if not arguments.acc and not arguments.mrn:
            raise ValueError("Must specify either ACCESSION or --mrn.")

    return arguments


def authenticate(url, cred_path):
    if cred_path:
        assert os.path.exists(cred_path), (
            f"AIR credential file ({cred_path}) does not exist."
        )
        envs = dotenv_values(cred_path)
        userId = envs["AIR_USERNAME"]
        password = envs["AIR_PASSWORD"]
    else:
        userId = os.environ.get("AIR_USERNAME")
        password = os.environ.get("AIR_PASSWORD")
        assert (userId and password) is not None, "AIR credentials not provided."
    auth_info = {"userId": userId, "password": password}

    session = requests.post(urljoin(url, "login"), json=auth_info).json()
    jwt = session["token"]["jwt"]

    projects = session["user"]["projects"]
    return jwt, projects


def get_deid_profiles(url, cred_path):
    jwt, _ = authenticate(url, cred_path)

    header = {"Authorization": "Bearer " + jwt}
    profiles = requests.post(
        urljoin(url, "secure/anonymization/list-profiles"),
        headers=header,
        json={
            "includeGlobal": True,
            "includeCustom": True,
            "includeDefault": False,
            "includeInactiveCustom": False,
            "includeInactiveGlobal": False,
            "includeInactiveShared": False,
            "includeShared": True,
        },
    ).json()
    ret = []
    for profile in profiles:
        ret.append({k: profile[k] for k in ("id", "name", "description")})
    return ret


def list_projects(url: str, cred_path: str) -> None:
    """List available project IDs from the API.

    Args:
        url (str): URL for AIR API.
        cred_path (str): Path to the credentials file.
    """
    _, projects = authenticate(url, cred_path)
    print("Available projects:")
    for project in projects:
        print(f"ID: {project['id']}, Name: {project['name']}")


def list_profiles(url: str, cred_path: str) -> None:
    """List available anonymization profiles from the API.

    Args:
        url (str): URL for AIR API.
        cred_path (str): Path to the credentials file.
    """
    profiles = get_deid_profiles(url, cred_path)
    print("Available anonymization profiles:")
    for profile in profiles:
        print(
            f"ID: {profile['id']}, Name: {profile['name']}, Description: {profile['description']}"
        )


def _build_exam_output_path(base_output: Path, exam: dict, exam_index: int) -> Path:
    """Generate a unique output path for each exam in case multiple are found.

    Args:
        base_output (Path): The user-provided output path.
        exam (dict): The exam object from the API.
        exam_index (int): Index of the current exam in the loop.

    Returns:
        Path: The updated output path for this exam.
    """
    # - p exists and is dir: create p / accession.zip
    # - p does not exist and has .zip extension: return p
    # - p exists and has .zip extension: return p with index appended
    p = base_output
    if not p.suffix.lower().endswith(".zip"):
        # p is supposed to be a directory
        p.mkdir(parents=True, exist_ok=True)
        acc_num = exam.get("accessionNumber") or f"exam_{exam_index + 1}"
        return p / f"{acc_num}.zip"
    elif not p.exists() and p.suffix.lower().endswith(".zip"):
        return p
    else:
        # If user provided a filename, append index to avoid overwriting
        stem = p.stem
        suffix = p.suffix
        return p.with_name(f"{stem}_{exam_index + 1}{suffix}")


def apply_inclusion_filter(
    items: List[Dict[str, Any]], field_name: str, patterns: str
) -> List[Dict[str, Any]]:
    """
    Filter items by partial match in the specified field for any of the comma-separated
    patterns (case-insensitive).
    Args:
        items (List[Dict[str, Any]]): A list of dictionaries to be filtered.
        field_name (str): The key in the dictionaries to apply the filter on.
        patterns (str): A comma-separated string of patterns to filter by.
    Returns:
        List[Dict[str, Any]]: A list of dictionaries that match any of the patterns in
        the specified field.
    """
    if not patterns:
        return items
    pattern_list = [p.strip().lower() for p in patterns.split(",")]
    original_count = len(items)
    print(f"Available {field_name}s:", set([i[field_name] for i in items]))
    filtered = [
        i
        for i in items
        if i.get(field_name) and any(p in i[field_name].lower() for p in pattern_list)
    ]
    print(
        f"{field_name.capitalize()} filter: from {original_count} originally to {len(filtered)}."
    )
    return filtered


def download(
    url: str,
    cred_path: str,
    accession: str,
    project: int,
    profile: int,
    output: Path = None,
    mrn: str = None,
    exam_modality_inclusion: str = None,
    exam_description_inclusion: str = None,
    series_inclusion: str = None,
    only_return_accessions: bool = False,
) -> None:
    """Download the DICOM data from AIR by accession or MRN, handling multiple exams if found."""
    jwt, _ = authenticate(url, cred_path)
    header = {"Authorization": "Bearer " + jwt}

    search_params = {
        "name": "",
        "mrn": mrn if mrn else "",
        "accNum": accession if accession else "",
        "dateRange": {"start": "", "end": "", "label": ""},
        "modality": "",
        "sourceId": 1,
    }
    exams = requests.post(
        urljoin(url, "secure/search/query-data-source"),
        headers=header,
        json=search_params,
    ).json()["exams"]

    exams = apply_inclusion_filter(exams, "modality", exam_modality_inclusion)
    exams = apply_inclusion_filter(exams, "description", exam_description_inclusion)

    if len(exams) == 0:
        print("No exams found, check your search parameters.")
        return

    if only_return_accessions:
        output_csv = output / "accessions.csv"
        print(f"Writing accessions to {output_csv}")
        with open(output_csv, "a+") as f:
            for exam in exams:
                f.write(
                    f'{mrn},{exam["accessionNumber"]},{exam["dateTime"]},{exam["sex"]},{exam["birthdate"]},"{exam["description"]}",{exam["imageCount"]}\n'
                )
        print("Accessions written to file.")
        return

    for i, study in tqdm(
        enumerate(exams), desc="Downloading exams", leave=True, total=len(exams)
    ):
        # Build a unique output path for each exam
        exam_output_fp = _build_exam_output_path(output, study, i)
        series = requests.post(
            urljoin(url, "secure/search/series"), headers=header, json=study
        ).json()

        series = apply_inclusion_filter(series, "description", series_inclusion)
        if len(series) == 0:
            print(
                f"No series found for {exam_output_fp.stem}. "
                "Check your search parameters."
            )
            continue

        def has_started(download_info):
            if "downloadId" not in download_info:
                if "project" in download_info["reason"]:
                    print("Project ID is invalid or missing. Available projects:")
                    list_projects(url, cred_path)
                elif "profile" in download_info["reason"]:
                    print("Profile ID is invalid or missing. Available profiles:")
                    list_profiles(url, cred_path)
                else:
                    print("Unknown error occurred during download initiation.")
                raise RuntimeError(f"Download failed. Server Response: {download_info}")
            check = requests.post(
                urljoin(url, "secure/search/download/check"),
                headers=header,
                json={"downloadId": download_info["downloadId"], "projectId": project},
            ).json()
            return check["status"] in ["started", "completed"]

        download_info = requests.post(
            urljoin(url, "secure/search/download/start"),
            headers=header,
            json={
                "decompress": False,
                "name": "Download.zip",
                "profile": profile,
                "projectId": project,
                "series": series,
                "study": study,
            },
        ).json()

        while not has_started(download_info):
            time.sleep(0.1)

        download_stream = requests.post(
            urljoin(url, "secure/search/download/zip"),
            headers={"Upgrade-Insecure-Requests": "1"},
            data={
                "params": json.dumps(
                    {
                        "downloadId": download_info["downloadId"],
                        "projectId": project,
                        "name": "Download.zip",
                    }
                ),
                "jwt": jwt,
            },
            stream=True,
        )

        total_size = int(download_stream.headers.get("Content-Length", 0))
        with (
            open(exam_output_fp, "wb") as fd,
            tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=f"Downloading accession {exam_output_fp.stem}",
                leave=False,
            ) as progress_bar,
        ):
            for chunk in download_stream.iter_content(chunk_size=8192):
                if chunk:
                    fd.write(chunk)
                    progress_bar.update(len(chunk))


def main(args):
    if args.list_projects and args.list_profiles:
        list_projects(args.url, args.cred_path)
        print()
        list_profiles(args.url, args.cred_path)
    elif args.list_projects:
        list_projects(args.url, args.cred_path)
    elif args.list_profiles:
        list_profiles(args.url, args.cred_path)
    else:
        download(
            url=args.url,
            accession=args.acc,
            cred_path=args.cred_path,
            output=args.output,
            project=args.project,
            profile=args.profile,
            series_inclusion=args.series_inclusion,
            mrn=args.mrn,
            exam_modality_inclusion=args.exam_modality_inclusion,
            exam_description_inclusion=args.exam_description_inclusion,
            only_return_accessions=args.only_return_accessions,
        )


def cli():
    main(parse_args())

if __name__ == "__main__":
    cli()
