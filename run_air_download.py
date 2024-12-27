#!/bin/python
import os
import subprocess
from pathlib import Path
import getpass
import argparse

CRED_PERMISSION_LEVEL = 0o600
AIR_API_URL = ""  # add info here
DEFAULT_PROJECT_ID = ""  # add info here
DEFAULT_ANONYMIZATION_PROFILE = ""  # add info here


def get_args():
    """Set up the argument parser and return the parsed arguments."""
    parser = argparse.ArgumentParser(
        description="Command line interface to the UCSF Automated Image Retrieval (AIR) Portal.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "accession",
        nargs="?",
        metavar="ACCESSION",
        help=(
            "Accession # to download, or path to csv file with accession #s "
            "in one column."
        ),
    )
    parser.add_argument(
        "-mrn", "--mrn", help="Patient ID to download"
    )
    parser.add_argument(
        "-o", "--output", help="Output path", default="./<Accession>.zip"
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
        "-pf",
        "--profile",
        help="Anonymization Profile",
        default=DEFAULT_ANONYMIZATION_PROFILE,
    )
    parser.add_argument(
        "-pj", "--project", help="Project ID", default=DEFAULT_PROJECT_ID
    )
    parser.add_argument(
        "-c",
        "--cred-path",
        help="Login credentials file. If not present, will prompt for AIR_USERNAME and AIR_PASSWORD.",
        default=Path.home() / "air_login.txt",
    )
    parser.add_argument(
        "-lpj", "--list-projects", action="store_true", help="List available project IDs"
    )
    parser.add_argument(
        "-lpf", "--list-profiles", action="store_true", help="List available anonymization profiles"
    )

    return parser.parse_args()


def set_credentials(cred_path=None):
    """Set the AIR_USERNAME and AIR_PASSWORD environment variables."""
    if cred_path is None:
        # Default to checking ~/air_login.txt if no cred_path is provided
        cred_path = Path.home() / "air_login.txt"

    cred_file = Path(cred_path).resolve()

    if cred_file.exists():
        if not cred_file.is_file():
            print(f"'{cred_path}' is not a file.")
            exit(1)

        if oct(cred_file.stat().st_mode)[-3:] != "600":
            print(
                f"Warning: '{cred_path}' does not have read/write-only permissions "
                "for the user (600)."
            )
            try:
                cred_file.chmod(CRED_PERMISSION_LEVEL)
                print(
                    "Permissions changed to read/write-only for the user (600) for "
                    f"'{cred_path}'."
                )
            except Exception as e:
                print(f"Failed to change permissions: {e}")
                exit(1)

        from dotenv import dotenv_values

        envs = dotenv_values(cred_path)
        os.environ["AIR_USERNAME"] = envs["AIR_USERNAME"]
        os.environ["AIR_PASSWORD"] = envs["AIR_PASSWORD"]

    else:
        username = input("Enter AIR_USERNAME: ")
        password = getpass.getpass("Enter AIR_PASSWORD: ")
        os.environ["AIR_USERNAME"] = username
        os.environ["AIR_PASSWORD"] = password

        # Ask the user if they want to save the credentials
        save_credentials = (
            input(
                "Do you want to save these credentials to a secure file in your "
                "home directory? (important for using this as script) (y/n): "
            )
            .strip()
            .lower()
        )

        if save_credentials == "y":
            try:
                cred_file.touch(CRED_PERMISSION_LEVEL)
                with cred_file.open("w") as f:
                    f.write(f"AIR_USERNAME={username}\n")
                    f.write(f"AIR_PASSWORD={password}\n")

                # Double check the file permissions to 600 (r/w for the user only)
                cred_file.chmod(CRED_PERMISSION_LEVEL)
                print(
                    f"Credentials saved to '{cred_file}' with secure permissions (600)."
                )
            except Exception as e:
                print(f"Warning: Failed to save credentials: {e}")


def get_output_directory(output_path, accession):
    """Determine the output directory based on the provided output path."""
    output_path = Path(output_path.replace("<Accession>", accession))
    if not output_path.is_dir():
        output_path = output_path.parent

    return output_path.resolve()


def run_container(args):
    """Run the Apptainer container with the provided arguments."""
    accession_csv = Path(args.accession)
    if accession_csv.is_file() and accession_csv.exists():
        accession_list = accession_csv.read_text().strip().split("\n")
    else:
        accession_list = [args.accession]

    output_dir = get_output_directory(args.output, args.accession[0])

    for accession in accession_list:
        command = [
            "apptainer",
            "run",
            "--bind",
            f"{output_dir}:{output_dir}",
            "air_download.sif",
            AIR_API_URL,
            args.accession,
            "-o",
            args.output,
            "-pf",
            args.profile,
            "-pj",
            args.project,
        ]

        if args.series_inclusion:
            command.extend(["-s", args.series_inclusion])
        if args.list_projects:
            command.append("-lpj")
        if args.list_profiles:
            command.append("-lpf")
        if args.mrn:
            command.extend(["-mrn", args.mrn])

        subprocess.run(command)


def main():
    args = get_args()
    set_credentials(args.cred_path)
    run_container(args)


if __name__ == "__main__":
    main()
