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
        "-o", "--output", help="Output path or directory", default="./<Accession>.zip"
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

    arguments = parser.parse_args()

    if not (arguments.list_projects or arguments.list_profiles):
        assert arguments.url, "URL to API address is required."
        assert (
            arguments.acc
        ), "Accession is required unless listing projects or profiles."

    if arguments.output == "./<Accession>.zip":
        arguments.output = f"{arguments.acc}.zip"
    elif Path(arguments.output).is_dir():
        arguments.output = str(Path(arguments.output) / f"{arguments.acc}.zip")
        print("Output path is a directory. Saving to: ", arguments.output, flush=True)

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


def download(
    url, cred_path, accession, output, project, profile, series_inclusion=None
):
    jwt, _ = authenticate(url, cred_path)
    header = {"Authorization": "Bearer " + jwt}

    # Search for study by accession number
    study = requests.post(
        urljoin(url, "secure/search/query-data-source"),
        headers=header,
        json={
            "name": "",
            "mrn": "",
            "accNum": accession,
            "dateRange": {"start": "", "end": "", "label": ""},
            "modality": "",
            "sourceId": 1,
        },
    ).json()["exams"][0]

    # Make a list of all included series
    series = requests.post(
        urljoin(url, "secure/search/series"), headers=header, json=study
    ).json()

    # Filter series based on inclusion patterns, if provided
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
            raise RuntimeError(f"download failed. Server Response: {download_info}")
        check = requests.post(
            urljoin(url, "secure/search/download/check"),
            headers=header,
            json={"downloadId": download_info["downloadId"], "projectId": project},
        ).json()
        return check["status"] in ["started", "completed"]

    # Prepare download job
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

    # Ensure that archive is ready for download
    while not has_started(download_info):
        time.sleep(0.1)

    # Download archive
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

    # Get total size from headers (probably not available though)
    total_size = int(download_stream.headers.get("Content-Length", 0))

    # Save archive to disk with a progress bar
    with (
        open(output, "wb") as fd,
        tqdm(
            total=total_size, unit="B", unit_scale=True, desc=output, leave=False
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
            args.url,
            args.cred_path,
            args.acc,
            args.output,
            args.project,
            args.profile,
            args.series_inclusion,
        )


def cli():
    main(parse_args())
