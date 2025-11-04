# SPDX-License-Identifier: GPL-2.0-or-later

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def change_working_directory():
    """Change working directory to tests/ for all tests."""
    # Get the directory where this conftest.py is located (tests/)
    # this fixture allows calling pytest from project root
    tests_dir = Path(__file__).resolve().parent
    os.chdir(tests_dir)
