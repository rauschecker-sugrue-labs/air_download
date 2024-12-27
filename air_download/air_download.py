import os
import argparse
from pathlib import Path
import time
import json
import requests
from dotenv import dotenv_values
from tqdm import tqdm
from urllib.parse import urljoin


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
        "-s",
        "--series_inclusion",
        help=(
            "Comma-separated list of series inclusion patterns (case insensitive, 'or' "
            "logic). Example for T1 type series: 't1,spgr,bravo,mpr'"
        ),
        default=None,
    )
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

    arguments = parser.parse_args()

    if not (arguments.list_projects or arguments.list_profiles):
        # At least one of 'acc' or 'mrn' must be provided
        if not arguments.acc and not arguments.mrn:
            raise ValueError("Must specify either ACCESSION or --mrn.")

    return arguments


def authenticate(url, cred_path):
    if cred_path:
        assert os.path.exists(
            cred_path
        ), f"AIR credential file ({cred_path}) does not exist."
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
        return str(p / f"{acc_num}.zip")
    elif not p.exists() and p.suffix.lower().endswith(".zip"):
        return str(p)
    else:
        # If user provided a filename, append index to avoid overwriting
        stem = p.stem
        suffix = p.suffix
        return str(p.with_name(f"{stem}_{exam_index + 1}{suffix}"))


def download(
    url: str,
    cred_path: str,
    accession: str,
    project: int,
    profile: int,
    output: Path = None,
    series_inclusion: str = None,
    mrn: str = None,
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
    
    if len(exams) > 1:
        print(f"Found {len(exams)} exams.")
    
    for i, study in enumerate(exams):
        # Build a unique output path for each exam
        exam_output_fp = _build_exam_output_path(output, study, i)
        exam_output_fp = Path(exam_output_fp)
        series = requests.post(
            urljoin(url, "secure/search/series"), headers=header, json=study
        ).json()

        if series_inclusion:
            inclusion_list = [
                pattern.strip().lower() for pattern in series_inclusion.split(",")
            ]
            original_series_description = [serie["description"] for serie in series]
            series = [
                serie
                for serie in series
                if (
                    serie["description"]
                    and any(
                        pattern in serie["description"].lower()
                        for pattern in inclusion_list
                    )
                )
            ]
            final_series_description = [serie["description"] for serie in series]
            print(f"Original series (n={len(original_series_description)}): ")
            print(original_series_description)
            print(f"Series after filtering (n={len(final_series_description)}): ")
            print(final_series_description)

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
        )


def cli():
    main(parse_args())
