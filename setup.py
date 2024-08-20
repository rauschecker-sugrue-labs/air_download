from setuptools import setup

setup(
    name='air_download',
    version='0.2.0',
    url='https://github.com/rauschecker-sugrue-labs/air_download',
    author='Pierre Nedelec',
    description='Command line interface to the Automated Image Retrieval (AIR) Portal. Originally developed by John Colby.',
    packages=['air_download'],
    install_requires=['requests', 'python-dotenv', 'tqdm'],
    entry_points={'console_scripts': ['air_download = air_download.air_download:cli']},
)