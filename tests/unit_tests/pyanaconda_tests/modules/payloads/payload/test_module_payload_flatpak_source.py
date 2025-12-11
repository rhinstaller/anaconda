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
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import urlparse

import pytest
import requests

from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.flatpak.source import (
    FlatpakRegistrySource,
    FlatpakStaticSource,
    RegistrySourceImage,
    StaticSourceImage,
)


class FlatpakStaticSourceTestCase(unittest.TestCase):
    """Test FlatpakStaticSource of the Flatpak module."""

    def _prepare_repo_data(self, url):
        data = RepoConfigurationData()
        data.url = url

        return data

    def _create_static_source_image(self, layer_download_sizes, install_size, ref):
        """Generate a Static Source Image with a correct json."""
        layers = []
        manifest_json = {"layers": layers}

        for layer_size in layer_download_sizes:
            layers.append({"size": str(layer_size)})

        config_json = {
            "config": {
                "Labels": {
                    "org.flatpak.installed-size": str(install_size),
                    "org.flatpak.ref": ref,
                }
            }
        }

        return StaticSourceImage(
            digest=0, manifest_json=manifest_json, config_json=config_json
        )

    def test_local_download(self):
        """Test FlatpakStaticSource for local source."""
        data = self._prepare_repo_data("file:///local/source")

        source = FlatpakStaticSource(data, "test-flatpak")
        ret = source.download(
            refs=["org.example.App"],
            download_location="/var/do/not/exist"
        )

        assert ret == "oci:/local/source/test-flatpak"

    @patch.object(FlatpakStaticSource, "_images", new_callable=PropertyMock)
    def test_calculate_size_source(self, mocked_images):
        """Test FlatpakStaticSource calculate_size method with one source."""
        image1 = self._create_static_source_image(
            layer_download_sizes=[10],
            install_size=40,
            ref="app/org.example.App1/amd64/stable",
        )

        mocked_images.return_value = [image1]
        data = self._prepare_repo_data("http://example.com/flatpak")

        source = FlatpakStaticSource(data, "test-flatpak")

        download_size, installed_size = source.calculate_size(
            [
                "org.fedoraproject.Stable:app/org.example.App1/amd64/stable",
            ]
        )

        assert download_size == 10
        assert installed_size == 40

    @patch.object(FlatpakStaticSource, "_images", new_callable=PropertyMock)
    def test_calculate_size_two_sources(self, mocked_images):
        """Test FlatpakStaticSource calculate_size method with two sources."""
        image1 = self._create_static_source_image(
            layer_download_sizes=[10, 20],
            install_size=40,
            ref="app/org.example.App1/amd64/stable",
        )
        image2 = self._create_static_source_image(
            layer_download_sizes=[11, 22],
            install_size=60,
            ref="app/org.example.App2/amd64/stable",
        )

        mocked_images.return_value = [image1, image2]
        data = self._prepare_repo_data("http://example.com/flatpak")

        source = FlatpakStaticSource(data, "test-flatpak")

        download_size, installed_size = source.calculate_size(
            [
                "org.fedoraproject.Stable:app/org.example.App1/amd64/stable",
                "org.fedoraproject.Stable:app/org.example.App2/amd64/stable",
            ]
        )

        assert download_size == 10 + 20 + 11 + 22
        assert installed_size == 40 + 60

    @patch.object(FlatpakStaticSource, "_images", new_callable=PropertyMock)
    def test_calculate_size_less_refs(self, mocked_images):
        """Test FlatpakStaticSource calculate_size method with subset refs."""
        image1 = self._create_static_source_image(
            layer_download_sizes=[10, 20],
            install_size=40,
            ref="app/org.example.App1/amd64/stable",
        )
        image2 = self._create_static_source_image(
            layer_download_sizes=[11, 22],
            install_size=60,
            ref="app/org.example.App2/amd64/stable",
        )

        mocked_images.return_value = [image1, image2]
        data = self._prepare_repo_data("http://example.com/flatpak")

        source = FlatpakStaticSource(data, "test-flatpak")

        download_size, installed_size = source.calculate_size(
            [
                "org.fedoraproject.Stable:app/org.example.App1/amd64/stable",
            ]
        )

        assert download_size == 10 + 20
        assert installed_size == 40

    @patch.object(FlatpakStaticSource, "_images", new_callable=PropertyMock)
    def test_calculate_size_more_refs(self, mocked_images):
        """Test FlatpakStaticSource calculate_size method with superset refs."""
        image1 = self._create_static_source_image(
            layer_download_sizes=[10, 20],
            install_size=40,
            ref="app/org.example.App1/amd64/stable",
        )

        mocked_images.return_value = [image1]
        data = self._prepare_repo_data("http://example.com/flatpak")

        source = FlatpakStaticSource(data, "test-flatpak")

        download_size, installed_size = source.calculate_size(
            [
                "org.fedoraproject.Stable:app/org.example.App1/amd64/stable",
                "org.fedoraproject.Stable:app/org.example.App2/amd64/stable",
            ]
        )

        assert download_size == 10 + 20
        assert installed_size == 40

    @patch.object(FlatpakStaticSource, "_images", new_callable=PropertyMock)
    def test_calculate_size_local_source(self, mocked_images):
        """Test FlatpakStaticSource calculate_size method with local source."""
        image1 = self._create_static_source_image(
            layer_download_sizes=[10, 20],
            install_size=40,
            ref="app/org.example.App1/amd64/stable",
        )

        mocked_images.return_value = [image1]
        data = self._prepare_repo_data("file:///local/source")

        source = FlatpakStaticSource(data, "test-flatpak")

        download_size, installed_size = source.calculate_size(
            [
                "org.fedoraproject.Stable:app/org.example.App1/amd64/stable",
            ]
        )

        # no download size for local image
        assert download_size == 0
        assert installed_size == 40


class FlatpakRegistrySourceTestCase(unittest.TestCase):
    """Test FlatpakRegistrySource of the Flatpak module."""

    def test_download(self):
        """Test FlatpakRegistrySource download method."""
        source = FlatpakRegistrySource("app/org.example.App1")
        assert source.download("", "") is None

    def _create_registry_source_image(self, download_size, install_size, ref):
        """Generate a Static Source Image with a correct json."""
        labels = {
            "org.flatpak.download-size": str(download_size),
            "org.flatpak.installed-size": str(install_size),
            "org.flatpak.ref": ref,
        }

        return RegistrySourceImage(labels)

    @patch.object(FlatpakRegistrySource, "_images", new_callable=PropertyMock)
    def test_calculate_size(self, mocked_images):
        """Test FlatpakRegistrySource calculate size with one source."""
        image = self._create_registry_source_image(
            download_size=20,
            install_size=30,
            ref="app/org.example.App1/amd64/stable"
        )
        mocked_images.return_value = [image]

        source = FlatpakRegistrySource("")

        # the outcome is the biggest download size and sum of install sizes taken as installed size
        # because flatpaks are installed one by one to the same storage as they are installed
        assert source.calculate_size(["app/org.example.App1/amd64/stable"]) == (0, 20 + 30)

    @patch.object(FlatpakRegistrySource, "_images", new_callable=PropertyMock)
    def test_calculate_size_two_sources(self, mocked_images):
        """Test FlatpakRegistrySource calculate size with two sources."""
        image = self._create_registry_source_image(
            download_size=20,
            install_size=30,
            ref="app/org.example.App1/amd64/stable"
        )
        image2 = self._create_registry_source_image(
            download_size=100,
            install_size=1000,
            ref="app/org.example.App2/amd64/stable"
        )
        mocked_images.return_value = [image, image2]

        source = FlatpakRegistrySource("")

        # the outcome is the biggest download size and sum of install sizes taken as installed size
        # because flatpaks are installed one by one to the same storage as they are installed
        refs = [
            "app/org.example.App1/amd64/stable",
            "app/org.example.App2/amd64/stable",
        ]
        assert source.calculate_size(refs) == (
            0,
            30 + 100 + 1000,
        )

    @patch.object(FlatpakRegistrySource, "_images", new_callable=PropertyMock)
    def test_calculate_size_less_refs(self, mocked_images):
        """Test FlatpakRegistrySource calculate size with subset refs."""
        image = self._create_registry_source_image(
            download_size=20,
            install_size=30,
            ref="app/org.example.App1/amd64/stable"
        )
        image2 = self._create_registry_source_image(
            download_size=100,
            install_size=1000,
            ref="app/org.example.App2/amd64/stable"
        )
        mocked_images.return_value = [image, image2]

        source = FlatpakRegistrySource("")

        # the outcome is the biggest download size and sum of install sizes taken as installed size
        # because flatpaks are installed one by one to the same storage as they are installed
        refs = [
            "app/org.example.App1/amd64/stable",
        ]
        assert source.calculate_size(refs) == (
            0,
            20 + 30,
        )

    @patch.object(FlatpakRegistrySource, "_images", new_callable=PropertyMock)
    def test_calculate_size_more_refs(self, mocked_images):
        """Test FlatpakRegistrySource calculate size with superset refs."""
        image = self._create_registry_source_image(
            download_size=20,
            install_size=30,
            ref="app/org.example.App1/amd64/stable"
        )
        mocked_images.return_value = [image]

        source = FlatpakRegistrySource("")

        # the outcome is the biggest download size and sum of install sizes taken as installed size
        # because flatpaks are installed one by one to the same storage as they are installed
        refs = [
            "app/org.example.App1/amd64/stable",
            "app/org.example.App2/amd64/stable",
        ]
        assert source.calculate_size(refs) == (
            0,
            20 + 30,
        )

    def test_get_request_keyword_args_no_certs(self):
        """Test _get_request_keyword_args with no certificates"""
        source = FlatpakRegistrySource("oci+https://example.com/flatpaks")
        parsed = urlparse("https://example.com")

        with patch("pathlib.Path.exists", return_value=False):
            kw = source._get_request_keyword_args(parsed)

        assert kw == {}

    def test_get_request_keyword_args_with_certs(self):
        """Test _get_request_keyword_args with certificates"""
        source = FlatpakRegistrySource("oci+https://satellite.example.com/flatpaks")
        parsed = urlparse("https://satellite.example.com")
        expected_base_path = Path("/etc/containers/certs.d/satellite.example.com")

        with patch("pathlib.Path.exists", return_value=True):
            kw = source._get_request_keyword_args(parsed)
        assert kw == {
            "cert": (expected_base_path / "client.cert", expected_base_path / "client.key"),
            "verify": expected_base_path / "ca-bundle.crt",
        }

    @patch("pyanaconda.modules.payloads.payload.flatpak.source.get_container_arch")
    @patch("pyanaconda.modules.payloads.payload.flatpak.source.requests_session")
    def test_images_ssl_self_signed_cert_fallback(self, mock_requests_session, mock_get_arch):
        """Test _images property with self-signed certificate fallback

        When a self-signed certificate error occurs, the code should retry with the
        updated ca-bundle.crt and successfully retrieve the images.
        """
        mock_get_arch.return_value = "amd64"

        # Mock session
        mock_session = MagicMock()
        mock_requests_session.return_value.__enter__.return_value = mock_session

        # Create SSL error for self-signed certificate
        ssl_error = requests.exceptions.SSLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
            "self-signed certificate in certificate chain"
        )

        # Mock first response that will raise SSL error on raise_for_status
        mock_first_response = MagicMock()
        mock_first_response.raise_for_status.side_effect = ssl_error

        # Mock successful response after retry
        mock_success_response = MagicMock()
        mock_success_response.json.return_value = {
            "Results": [
                {
                    "Images": [
                        {
                            "Architecture": "amd64",
                            "Labels": {
                                "org.flatpak.ref": "app/org.example.App/amd64/stable",
                                "org.flatpak.download-size": "1000",
                                "org.flatpak.installed-size": "2000",
                            },
                        }
                    ]
                }
            ]
        }

        # First call returns response that fails on raise_for_status, second call succeeds
        mock_session.get.side_effect = [mock_first_response, mock_success_response]

        source = FlatpakRegistrySource("oci+https://stage.cdn.example.com/flatpaks")

        # Access _images to trigger the property - should succeed after retry
        images = source._images

        # Verify we got the expected image
        assert len(images) == 1
        assert images[0].ref == "app/org.example.App/amd64/stable"
        assert images[0].download_size == 1000
        assert images[0].installed_size == 2000

        # Verify session.get was called twice (the retry happened)
        assert mock_session.get.call_count == 2

        # First call should use default kw args (empty dict in this case)
        first_call = mock_session.get.call_args_list[0]
        assert first_call[1] == {}

        # Second call should include verify with ca-bundle path (the retry used the updated cert)
        second_call = mock_session.get.call_args_list[1]
        assert second_call[1] == {"verify": "/etc/ssl/certs/ca-bundle.crt"}

    @patch("pyanaconda.modules.payloads.payload.flatpak.source.get_container_arch")
    @patch("pyanaconda.modules.payloads.payload.flatpak.source.requests_session")
    def test_images_ssl_error_non_self_signed_reraises(self, mock_requests_session, mock_get_arch):
        """Test _images property re-raises SSL errors that are not self-signed certificate errors"""
        mock_get_arch.return_value = "amd64"

        # Mock session
        mock_session = MagicMock()
        mock_requests_session.return_value.__enter__.return_value = mock_session

        # Create a different SSL error (not self-signed)
        ssl_error = requests.exceptions.SSLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"
        )

        mock_session.get.side_effect = ssl_error

        source = FlatpakRegistrySource("oci+https://example.com/flatpaks")

        # Access _images should re-raise the SSL error
        with pytest.raises(requests.exceptions.SSLError) as context:
            _ = source._images

        assert "certificate has expired" in str(context.value)

        # Verify session.get was called only once (no retry for non-self-signed errors)
        assert mock_session.get.call_count == 1
