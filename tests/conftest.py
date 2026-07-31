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


@pytest.fixture
def anaconda_run_dir(tmp_path, monkeypatch):
    """Set up an isolated /run/anaconda directory for tests."""
    rundir = tmp_path / "rundir"
    rundir.mkdir()
    monkeypatch.setenv("ANACONDA_RUN_DIR", str(rundir))
    return rundir
