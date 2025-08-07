#
# Copyright (C) 2020  Red Hat, Inc.
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
from unittest.case import TestCase

import pytest

from pyanaconda.core.kickstart.specification import (
    KickstartSpecificationHandler,
    KickstartSpecificationParser,
)
from pyanaconda.modules.payloads.constants import PayloadType
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.payloads.payload.factory import PayloadFactory
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.payload_base_interface import (
    PayloadBaseInterface,
)


class PayloadFactoryTestCase(TestCase):
    """Test the payload factory."""

    def test_create_payload(self):
        """Test PayloadFactory create method."""
        for payload_type in PayloadType:
            module = PayloadFactory.create_payload(payload_type)
            assert isinstance(module, PayloadBase)
            assert isinstance(module.for_publication(), PayloadBaseInterface)
            assert module.type == payload_type

    def test_failed_create_payload(self):
        """Test failed create method of the payload factory."""
        with pytest.raises(ValueError):
            PayloadFactory.create_payload("INVALID")

    def test_create_payload_from_ks(self):
        """Test PayloadFactory create from KS method."""
        self._check_payload_type(
            PayloadType.LIVE_IMAGE,
            "liveimg --url http://my/path"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "cdrom"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "hmc"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "harddrive --partition=Glum1 --dir=something/precious"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "nfs --server=ring.com --dir=Moria"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "url --url=lonely_mountain.erebor/GOLD!"
        )

        self._check_payload_type(
            PayloadType.RPM_OSTREE,
            "ostreesetup --osname=atomic --url=file:///repo --ref=fedora/atomic-host"
        )

        self._check_payload_type(
            PayloadType.BOOTC,
            "bootc --source-imgref=quay.io/centos-bootc/centos-bootc:stream9 --stateroot=default"
        )

        self._check_payload_type(
            PayloadType.DNF,
            "%packages\n%end"
        )

        self._check_payload_type(
            None,
            ""
        )

    def _check_payload_type(self, payload_type, kickstart):
        """Check the payload type for the given kickstart."""
        specification = PayloadKickstartSpecification
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)
        parser.readKickstartFromString(kickstart)
        assert payload_type == PayloadFactory.get_type_for_kickstart(handler)
