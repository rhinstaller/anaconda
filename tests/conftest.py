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
    error_file = str(rundir / "installation-error-msg")
    monkeypatch.setattr(
        "pyanaconda.core.constants.ANACONDA_INSTALL_ERROR_MSG_FILE",
        error_file,
    )
    return rundir


@pytest.fixture
def dnf_logdir(tmp_path, monkeypatch):
    """Replace /tmp/dnf.log with a temporary path."""
    # libdnf5 doesn't expose a way to change permissions in this log file
    # and it causes issues when running certain tests in a rootless container
    logdir = tmp_path / "dnflog"
    logdir.mkdir()
    # libdnf5 config setters require a str, they reject a Path.
    monkeypatch.setattr(
        "pyanaconda.modules.payloads.payload.dnf.dnf_manager.DNF_LOG_DIR",
        str(logdir),
    )
    return logdir


@pytest.fixture
def no_lvm_probe(monkeypatch):
    """Stop blivet from probing the host for real LVM information.

    blivet caches LVM state in process-global singletons, which shell out to
    lvs/pvs/vgs on first access. That needs device-mapper access, so in a
    rootless container it raises LVMError instead of returning empty data --
    even for tests that only exercise name-generation logic. Serving an empty
    cache keeps these tests hermetic and rootless.
    """
    from blivet.static_data.lvm_info import LVsInfo, PVsInfo, VGsInfo

    for cls in (LVsInfo, PVsInfo, VGsInfo):
        monkeypatch.setattr(cls, "cache", property(lambda x: {}))
