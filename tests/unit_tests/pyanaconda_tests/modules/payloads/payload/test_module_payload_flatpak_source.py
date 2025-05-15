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
from unittest.mock import PropertyMock, patch

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
