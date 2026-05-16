#
# Copyright (C) 2025 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pykickstart.errors import KickstartParseError

from pyanaconda.core.kickstart.specification import (
    KickstartSpecificationHandler,
    KickstartSpecificationParser,
)
from pyanaconda.modules.storage.disk_initialization import DiskInitializationModule
from pyanaconda.modules.storage.disk_selection import DiskSelectionModule
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification

ISCSI_INITIATOR = "iqn.2025-01.com.example:initiator"
ISCSI_TARGET = "iqn.2025-01.com.example:target0"
ISCSI_IP = "10.0.0.1"
ISCSI_PORT = 3260
ISCSI_DISK = "sda"

KS_ISCSI_BEFORE_IGNOREDISK = f"""\
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
ignoredisk --only-use={ISCSI_DISK}
"""

KS_IGNOREDISK_ONLYUSE_BEFORE_ISCSI = f"""\
ignoredisk --only-use={ISCSI_DISK}
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
"""

KS_IGNOREDISK_DRIVES_BEFORE_ISCSI = f"""\
ignoredisk --drives={ISCSI_DISK}
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
"""

KS_ISCSI_BEFORE_CLEARPART = f"""\
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
clearpart --drives={ISCSI_DISK}
"""

KS_CLEARPART_BEFORE_ISCSI = f"""\
clearpart --drives={ISCSI_DISK}
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
"""

KS_CLEARPART_LIST_BEFORE_ISCSI = f"""\
clearpart --list={ISCSI_DISK}
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
"""

KS_IGNOREDISK_NONEXISTENT = f"""\
iscsiname {ISCSI_INITIATOR}
iscsi --target={ISCSI_TARGET} --ipaddr={ISCSI_IP}
ignoredisk --only-use=nonexistent
"""


@contextmanager
def _parse_iscsi_kickstart(ks_content):
    """Parse a kickstart snippet with mocked iSCSI and device_matches.

    Uses a stateful mock: device_matches("sda") returns ["sda"] only
    after add_target has been called, simulating the disk appearing
    after iSCSI login.

    Yields inside the patch context so assertions run while mocks are
    still active — required because the fix defers validation to
    process_kickstart().
    """
    iscsi_connected = False

    def device_matches_side_effect(spec, disks_only=False):
        if spec == ISCSI_DISK and iscsi_connected:
            return [ISCSI_DISK]
        return []

    def add_target_side_effect(*_args, **_kwargs):
        nonlocal iscsi_connected
        iscsi_connected = True

    mock_iscsi = MagicMock()
    type(mock_iscsi).mode = PropertyMock(return_value="none")
    mock_iscsi.add_target.side_effect = add_target_side_effect

    with (
        patch(
            "pyanaconda.modules.storage.kickstart.device_matches",
            side_effect=device_matches_side_effect,
        ),
        patch(
            "pyanaconda.modules.storage.kickstart.iscsi",
            mock_iscsi,
        ),
        patch(
            "pyanaconda.modules.storage.kickstart.wait_for_network_devices",
            return_value=True,
        ),
    ):
        specification = StorageKickstartSpecification
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)

        parser.readKickstartFromString(ks_content)

        yield handler, mock_iscsi


def _assert_add_target_called(mock_iscsi):
    """Verify add_target was called with the expected iSCSI parameters."""
    mock_iscsi.add_target.assert_called_once()
    args, kwargs = mock_iscsi.add_target.call_args
    ipaddr, port, user, password, user_in, password_in = args
    assert ipaddr == ISCSI_IP
    assert port == ISCSI_PORT
    assert user is None
    assert password is None
    assert user_in is None
    assert password_in is None
    assert kwargs == {"target": ISCSI_TARGET, "iface": None}


@pytest.mark.parametrize(
    "ks_content",
    [
        pytest.param(KS_ISCSI_BEFORE_IGNOREDISK, id="iscsi-before-ignoredisk"),
        pytest.param(KS_IGNOREDISK_ONLYUSE_BEFORE_ISCSI, id="ignoredisk-onlyuse-before-iscsi"),
    ],
)
def test_ignoredisk_onlyuse_iscsi_ordering(ks_content):
    """ignoredisk --only-use with iSCSI disks must work regardless of command order.

    Reproducer for INSTALLER-4044 / RHEL-13837 / RHEL-58827.
    """
    with _parse_iscsi_kickstart(ks_content) as (handler, mock_iscsi):
        module = DiskSelectionModule()
        module.process_kickstart(handler)

        assert module.selected_disks == [ISCSI_DISK]
        assert module.ignored_disks == []
        assert mock_iscsi.initiator == ISCSI_INITIATOR
        _assert_add_target_called(mock_iscsi)


@pytest.mark.parametrize(
    "ks_content",
    [
        pytest.param(KS_IGNOREDISK_DRIVES_BEFORE_ISCSI, id="ignoredisk-drives-before-iscsi"),
    ],
)
def test_ignoredisk_drives_iscsi_ordering(ks_content):
    """ignoredisk --drives with iSCSI disks must work regardless of command order."""
    with _parse_iscsi_kickstart(ks_content) as (handler, mock_iscsi):
        module = DiskSelectionModule()
        module.process_kickstart(handler)

        assert module.selected_disks == []
        assert module.ignored_disks == [ISCSI_DISK]
        assert mock_iscsi.initiator == ISCSI_INITIATOR
        _assert_add_target_called(mock_iscsi)


@pytest.mark.parametrize(
    "ks_content",
    [
        pytest.param(KS_ISCSI_BEFORE_CLEARPART, id="iscsi-before-clearpart"),
        pytest.param(KS_CLEARPART_BEFORE_ISCSI, id="clearpart-before-iscsi"),
    ],
)
def test_clearpart_iscsi_ordering(ks_content):
    """clearpart --drives with iSCSI disks must work regardless of command order."""
    with _parse_iscsi_kickstart(ks_content) as (handler, mock_iscsi):
        module = DiskInitializationModule()
        module.process_kickstart(handler)

        assert module.drives_to_clear == [ISCSI_DISK]
        assert mock_iscsi.initiator == ISCSI_INITIATOR
        _assert_add_target_called(mock_iscsi)


def test_clearpart_list_iscsi_ordering():
    """clearpart --list with iSCSI devices must work regardless of command order."""
    with _parse_iscsi_kickstart(KS_CLEARPART_LIST_BEFORE_ISCSI) as (handler, mock_iscsi):
        module = DiskInitializationModule()
        module.process_kickstart(handler)

        assert module.devices_to_clear == [ISCSI_DISK]
        assert mock_iscsi.initiator == ISCSI_INITIATOR
        _assert_add_target_called(mock_iscsi)


def test_ignoredisk_nonexistent_device():
    """ignoredisk with a device that doesn't exist must still raise KickstartParseError."""
    with _parse_iscsi_kickstart(KS_IGNOREDISK_NONEXISTENT) as (handler, mock_iscsi):
        module = DiskSelectionModule()
        with pytest.raises(KickstartParseError, match="nonexistent"):
            module.process_kickstart(handler)
        _assert_add_target_called(mock_iscsi)
