# Automated Image Retrieval (AIR) Download

This is a small wrapper interface to the AIR web API. This will help you to batch download radiology studies if you have this service available on your PACS system.

## Install

Install the `air_download` package directly from the git repository like:

```bash
pip install git+https://github.com/johncolby/air_download
```

(modify URL if the repository lives somewhere other than github)

## Usage

```bash
air_download -c /path/to/air_login.txt https://air.<domain>.edu/api/ 11111111
```

Login credentials should be stored in a plain text file like:

```bash
AIR_USERNAME=username
AIR_PASSWORD=password
```

Please ensure this file is reasonably secure.

```bash
chmod 600 air_login.txt
```

Alternatively, credentials may be stored as environment variables like:

```bash
AIR_USERNAME=username
AIR_PASSWORD=password
export AIR_USERNAME AIR_PASSWORD

air_download https://air.<domain>.edu/api/ 11111111
```

Type `air_download -h` for the help text.

```bash
$ air_download -h
usage: air_download [-h] [-c CRED_PATH] [-p PROFILE] [-o OUTPUT] URL ACCESSION

positional arguments:
  URL                   URL for AIR API, e.g. https://air.<domain>.edu/api/
  ACCESSION             Accession # to download

optional arguments:
  -h, --help            show this help message and exit
  -c CRED_PATH, --cred_path CRED_PATH
                        Login credentials file. If not present, will look for
                        AIR_USERNAME and AIR_PASSWORD environment variables.
                        (default: None)
  -p PROFILE, --profile PROFILE
                        Anonymization Profile (default: -1)
  -o OUTPUT, --output OUTPUT
                        Output path (default: ./<Accession>.zip)
  -s SERIES_INCLUSION, --series_inclusion SERIES_INCLUSION
                        Comma separated list of strings for series sub-selection (default: None)
```

From within python, you can also import the module directly, so that it may be integrated with other tools.

```python
import air_download.air_download as air
import argparse

args = argparse.Namespace()
args.cred_path = '/path/to/air_login.txt'
args.URL       = 'https://air.<domain>.edu/api/'
args.acc       = '11111111'
args.profile   = -1
args.output    = '11111111.zip'

air.main(args)
```
