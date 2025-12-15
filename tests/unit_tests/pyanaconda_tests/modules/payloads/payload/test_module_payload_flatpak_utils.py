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
import ssl
import unittest
from unittest.mock import Mock, patch

import pytest

from pyanaconda.modules.payloads.payload.flatpak.utils import (
    canonicalize_flatpak_ref,
    get_container_arch,
    is_self_signed_certificate_error,
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


class IsSelfSignedCertificateErrorTestCase:
    @staticmethod
    def create_ssl_error(verify_code):
        """Create an SSLCertVerificationError with a specific verify_code."""
        exc = Mock(spec=ssl.SSLCertVerificationError)
        exc.verify_code = verify_code
        exc.__cause__ = None
        exc.args = []
        return exc

    def test_self_signed_cert_depth_zero(self):
        """Test detection of depth zero self-signed certificate error (code 18)."""
        exc = self.create_ssl_error(18)
        assert is_self_signed_certificate_error(exc) is True

    def test_self_signed_cert_in_chain(self):
        """Test detection of self-signed certificate in chain error (code 19)."""
        exc = self.create_ssl_error(19)
        assert is_self_signed_certificate_error(exc) is True

    def test_different_ssl_error_code(self):
        """Test non-self-signed SSL error returns False."""
        exc = self.create_ssl_error(20)
        assert is_self_signed_certificate_error(exc) is False

    def test_non_ssl_exception(self):
        """Test non-SSL exception returns False."""
        exc = ValueError("Some error")
        assert is_self_signed_certificate_error(exc) is False

    def test_self_signed_cert_in_cause_chain(self):
        """Test detection when SSLCertVerificationError is in __cause__ chain."""
        try:
            try:
                raise ssl.SSLCertVerificationError("Self-signed cert")
            except ssl.SSLCertVerificationError as ssl_exc:
                ssl_exc.verify_code = 18
                raise ValueError("Connection failed") from ssl_exc
        except ValueError as outer_exc:
            assert is_self_signed_certificate_error(outer_exc) is True

    def test_self_signed_cert_in_args_chain(self):
        """Test detection when SSLCertVerificationError is in args[0] chain."""
        ssl_exc = self.create_ssl_error(19)

        outer_exc = Mock(spec=Exception, args=[ssl_exc], __cause__=None)
        assert is_self_signed_certificate_error(outer_exc) is True

    def test_deep_exception_chain_with_self_signed(self):
        """Test detection in a deep exception chain."""
        try:
            try:
                try:
                    raise ssl.SSLCertVerificationError("Self-signed cert")
                except ssl.SSLCertVerificationError as ssl_exc:
                    ssl_exc.verify_code = 18
                    raise RuntimeError("Middle error") from ssl_exc
            except RuntimeError as middle_exc:
                raise ValueError("Outer error") from middle_exc
        except ValueError as outer_exc:
            assert is_self_signed_certificate_error(outer_exc) is True

    def test_exception_chain_without_self_signed(self):
        """Test exception chain without self-signed certificate error returns False."""
        try:
            try:
                raise RuntimeError("Inner error")
            except RuntimeError as inner_exc:
                raise ValueError("Middle error") from inner_exc
        except ValueError as middle_exc:
            try:
                raise ConnectionError("Outer error") from middle_exc
            except ConnectionError as outer_exc:
                assert is_self_signed_certificate_error(outer_exc) is False

    def test_deep_exception_chain_with_self_signed_as_arg(self):
        """Test detection in a deep exception chain."""
        try:
            try:
                try:
                    raise ssl.SSLCertVerificationError("Self-signed cert")
                except ssl.SSLCertVerificationError as ssl_exc:
                    ssl_exc.verify_code = 18
                    # disabled pylint check because in this case we want to test when a exception
                    # is raised from another without 'from'
                    raise RuntimeError(ssl_exc, "Middle error") # pylint: disable=raise-missing-from
            except RuntimeError as middle_exc:
                raise ValueError("Outer error") from middle_exc
        except ValueError as outer_exc:
            assert is_self_signed_certificate_error(outer_exc) is True

    def test_ssl_error_with_different_code_in_chain(self):
        """Test SSL error with non-self-signed code in chain returns False."""
        try:
            try:
                raise ssl.SSLCertVerificationError("Different SSL error")
            except ssl.SSLCertVerificationError as ssl_exc:
                ssl_exc.verify_code = 10
                raise ValueError("Connection failed") from ssl_exc
        except ValueError as outer_exc:
            assert is_self_signed_certificate_error(outer_exc) is False

    def test_exception_with_empty_args(self):
        """Test exception with empty args and no __cause__ returns False."""
        exc = ValueError("Some error")
        exc.__cause__ = None
        exc.args = []

        assert is_self_signed_certificate_error(exc) is False

    def test_exception_with_string_args(self):
        """Test exception with string in args returns False."""
        exc = ValueError("Some error", "additional context")
        assert is_self_signed_certificate_error(exc) is False
