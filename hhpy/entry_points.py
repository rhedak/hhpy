"""
py_pkg.entry_points.py
~~~~~~~~~~~~~~~~~~~~~~

This module contains the entry-point functions for the py_pkg module,
that are referenced in setup.py.
"""

import os
import requests

from os import remove
from sys import argv
from zipfile import ZipFile


# get key package details from py_pkg/__version__.py
about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, '__version__.py')) as f:
    exec(f.read(), about)


def main() -> None:
    """Main package entry point.

    Delegates to other functions based on user input.
    """

    try:
        user_cmd = argv[1]
        if user_cmd == 'install':
            install_from_github()
        else:
            RuntimeError('please supply a command for py_pkg - e.g. install.')
    except IndexError:
        RuntimeError('please supply a command for py_pkg - e.g. install.')
    return None


def install_from_github() -> None:
    """Installs the latest version from git"""

    # check that the user really want to do this
    msg = 'Download Python package template project to this directory (y/n)? '
    user_response = input(msg)
    if user_response != 'y':
        return None

    # download ZIP archive of GitHub repository
    url = about['__download_url__']
    r = requests.get(url)
    with open('temp.zip', 'wb') as f:
        f.write(r.content)

    # extract ZIP file into calling directory
    with ZipFile('temp.zip', 'r') as repo_zip:
        repo_zip.extractall('.')

    # clean up
    remove('temp.zip')
    return None
