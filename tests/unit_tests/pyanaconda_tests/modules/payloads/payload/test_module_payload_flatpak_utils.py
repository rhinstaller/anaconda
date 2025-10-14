#
# Copyright (C) 2025  Red Hat, Inc.
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
# Red Hat Author(s): Jiri Konecny <jkonecny@redhat.com>
#
import unittest
from unittest.mock import patch

import pytest

from pyanaconda.modules.payloads.payload.flatpak.utils import (
    canonicalize_flatpak_ref,
    get_container_arch,
)


class FlatpakUtilsTestCase(unittest.TestCase):
    """Test flatpak module utility functions."""

    @patch("pyanaconda.modules.payloads.payload.flatpak.utils.get_arch")
    def test_get_container_arch(self, get_arch):
        """Test get_container_arch function."""

        get_arch.return_value = "x86_64"
        assert get_container_arch() == "amd64"

        get_arch.return_value = "aarch64"
        assert get_container_arch() == "arm64"

    # Assisted by watsonx Code Assistant
    @patch("pyanaconda.modules.payloads.payload.flatpak.utils.get_arch")
    def test_canonicalize_flatpak_ref(self, get_arch_mock):
        """Test canonicalize_flatpak_ref function."""
        get_arch_mock.return_value = "x86_64"

        ref = "org.fedoraproject.Stable:app/org.example.Foo//stable"
        collection, ref = canonicalize_flatpak_ref(ref)
        assert collection == "org.fedoraproject.Stable"
        assert ref == "app/org.example.Foo/x86_64/stable"

        ref = "app/org.example.Foo//stable"
        collection, ref = canonicalize_flatpak_ref(ref)
        assert collection is None
        assert ref == "app/org.example.Foo/x86_64/stable"

        ref = "app/org.example.Foo/arm64/stable"
        collection, ref = canonicalize_flatpak_ref(ref)
        assert collection is None
        assert ref == "app/org.example.Foo/arm64/stable"

        ref = "org.example.Foo//stable"
        with pytest.raises(RuntimeError):
            canonicalize_flatpak_ref(ref)
