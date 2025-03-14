#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import os
import tempfile
import unittest
from textwrap import dedent
from unittest.mock import patch

import pytest
from blivet.size import Size
from pykickstart.constants import AUTOPART_TYPE_BTRFS

from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.configuration.base import (
    ConfigurationError,
    create_parser,
    read_config,
)
from pyanaconda.core.configuration.profile import ProfileLoader
from pyanaconda.modules.storage.partitioning.automatic.utils import (
    get_default_partitioning,
)
from pyanaconda.modules.storage.partitioning.specification import PartSpec

PROFILE_DIR = os.path.join(os.environ.get("ANACONDA_DATA"), "profile.d")

SERVER_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("2GiB"),
        max_size=Size("15GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    )
]

WORKSTATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("70GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("500MiB"), grow=True,
        required_space=Size("50GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
]

WORKSTATIONPLUS_PARTITIONING = WORKSTATION_PARTITIONING + [
    PartSpec(
        mountpoint="/var",
        # size=Size("15GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
        schemes={AUTOPART_TYPE_BTRFS}
    ),
]

ENTERPRISE_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("1GiB"),
        max_size=Size("70GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("500MiB"), grow=True,
        required_space=Size("50GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True
    ),
]

VIRTUALIZATION_PARTITIONING = [
    PartSpec(
        mountpoint="/",
        size=Size("6GiB"),
        grow=True,
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/home",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/tmp",
        size=Size("1GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var",
        size=Size("5GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/crash",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/log",
        size=Size("8GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/log/audit",
        size=Size("2GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        mountpoint="/var/tmp",
        size=Size("10GiB"),
        btr=True,
        lv=True,
        thin=True,
        encrypted=True,
    ),
    PartSpec(
        fstype="swap",
        lv=True,
        encrypted=True,
    )
]


class ProfileConfigurationTestCase(unittest.TestCase):
    """Test the default profile configurations."""

    def setUp(self):
        """Set up the default loader."""
        self.maxDiff = None
        self._loader = ProfileLoader()
        self._loader.load_profiles(PROFILE_DIR)

    def _load_profile(self, content):
        """Load a profile configuration with the given content."""
        with tempfile.NamedTemporaryFile("w") as f:
            f.write(content)
            f.flush()

            self._loader.load_profile(f.name)
            return f.name

    def _check_profile(self, profile_id, file_paths):
        """Check a profile."""
        assert self._loader.check_profile(profile_id)
        assert self._loader.collect_configurations(profile_id) == file_paths

    def _check_detection(self, profile_id, os_id, variant_id):
        """Check the profile detection."""
        assert self._loader.detect_profile(os_id, variant_id) == profile_id

    def _check_partitioning(self, config, partitioning):
        with patch("pyanaconda.modules.storage.partitioning.automatic.utils.platform") as platform:
            platform.partitions = []

            with patch("pyanaconda.modules.storage.partitioning.automatic.utils.conf", new=config):
                default = get_default_partitioning()
                print("Default: " + repr(default))
                print("Supplied: " + repr(partitioning))
                assert default == partitioning

    def _check_default_profile(self, profile_id, os_release_values, file_names, partitioning):
        """Check a default profile."""
        paths = [os.path.join(PROFILE_DIR, path) for path in file_names]
        self._check_profile(profile_id, paths)

        config = AnacondaConfiguration.from_defaults()
        paths = self._loader.collect_configurations(profile_id)

        for path in paths:
            config.read(path)

        config.validate()

        self._check_detection(profile_id, *os_release_values)
        self._check_partitioning(config, partitioning)
        assert "{}.conf".format(profile_id) == file_names[-1]

    def _get_config(self, profile_id):
        """Get parsed config file."""
        config = AnacondaConfiguration.from_defaults()
        paths = self._loader.collect_configurations(profile_id)

        for path in paths:
            config.read(path)

        config.validate()

        return config

    def test_fedora_profiles(self):
        self._check_default_profile(
            "fedora",
            ("fedora", ""),
            ["fedora.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_profile(
            "fedora-server",
            ("fedora", "server"),
            ["fedora.conf", "fedora-server.conf"],
            SERVER_PARTITIONING
        )
        self._check_default_profile(
            "fedora-workstation",
            ("fedora", "workstation"),
            ["fedora.conf", "fedora-workstation.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_profile(
            "fedora-silverblue",
            ("fedora", "silverblue"),
            ["fedora.conf", "fedora-workstation.conf", "fedora-silverblue.conf"],
            WORKSTATIONPLUS_PARTITIONING
        )
        self._check_default_profile(
            "fedora-kde",
            ("fedora", "kde"),
            ["fedora.conf", "fedora-kde.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_profile(
            "fedora-kinoite",
            ("fedora", "kinoite"),
            ["fedora.conf", "fedora-kde.conf", "fedora-kinoite.conf"],
            WORKSTATIONPLUS_PARTITIONING
        )
        self._check_default_profile(
            "fedora-sericea",
            ("fedora", "sericea"),
            ["fedora.conf", "fedora-sericea.conf"],
            WORKSTATIONPLUS_PARTITIONING
        )
        self._check_default_profile(
            "fedora-designsuite",
            ("fedora", "designsuite"),
            ["fedora.conf", "fedora-workstation.conf", "fedora-designsuite.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_profile(
            "fedora-iot",
            ("fedora", "iot"),
            ["fedora.conf", "fedora-iot.conf"],
            WORKSTATION_PARTITIONING
        )
        self._check_default_profile(
            "fedora-eln",
            ("fedora", "eln"),
            ["rhel.conf", "fedora-eln.conf"],
            ENTERPRISE_PARTITIONING
        )

    def test_rhel_profiles(self):
        self._check_default_profile(
            "rhel",
            ("rhel", ""),
            ["rhel.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "centos",
            ("centos", ""),
            ["rhel.conf", "centos.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "rhvh",
            ("rhel", "ovirt-node"),
            ["rhel.conf", "rhvh.conf"],
            VIRTUALIZATION_PARTITIONING
        )
        self._check_default_profile(
            "ovirt",
            ("centos", "ovirt-node"),
            ["rhel.conf", "centos.conf", "ovirt.conf"],
            VIRTUALIZATION_PARTITIONING
        )
        self._check_default_profile(
            "scientific-linux",
            ("scientific", ""),
            ["rhel.conf", "scientific-linux.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "almalinux",
            ("almalinux", ""),
            ["rhel.conf", "almalinux.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "rocky",
            ("rocky", ""),
            ["rhel.conf", "rocky.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "virtuozzo-linux",
            ("virtuozzo", ""),
            ["rhel.conf", "virtuozzo-linux.conf"],
            ENTERPRISE_PARTITIONING
        )
        self._check_default_profile(
            "circle",
            ("circle", ""),
            ["rhel.conf", "circle.conf"],
            ENTERPRISE_PARTITIONING
        )

    def _compare_profile_files(self, file_name, other_file_name, ignored_sections=()):
        parser = create_parser()
        read_config(parser, os.path.join(PROFILE_DIR, file_name))

        other_parser = create_parser()
        read_config(other_parser, os.path.join(PROFILE_DIR, other_file_name))

        # Ignore the specified and profile-related sections.
        ignored_sections += ("Profile", "Profile Detection")

        sections = set(parser.sections()).difference(ignored_sections)
        other_sections = set(other_parser.sections()).difference(ignored_sections)

        # Otherwise, the defined sections should be the same.
        assert sections == other_sections

        for section in sections:
            # The defined options should be the same.
            assert parser.options(section) == other_parser.options(section)

            for key in parser.options(section):
                # The values of the options should be the same.
                assert parser.get(section, key) == other_parser.get(section, key)

    def test_ovirt_and_rhvh(self):
        """Test the similarity of oVirt Node Next with Red Hat Virtualization Host."""
        self._compare_profile_files("rhvh.conf", "ovirt.conf", ignored_sections=("License", ))

    def test_valid_profile(self):
        content = dedent("""
        [Profile]
        profile_id = custom-profile
        """)

        base_path = self._load_profile(content)
        self._check_profile("custom-profile", [base_path])

        content = dedent("""
        [Profile]
        profile_id = another-profile
        base_profile = custom-profile
        """)

        path = self._load_profile(content)
        self._check_profile("another-profile", [base_path, path])

    def test_profile_detection(self):
        content = dedent("""
        [Profile]
        profile_id = undetectable-profile
        """)
        self._load_profile(content)

        content = dedent("""
        [Profile]
        profile_id = custom-profile

        [Profile Detection]
        os_id = custom-os
        """)
        self._load_profile(content)

        content = dedent("""
        [Profile]
        profile_id = another-profile
        base_profile = custom-profile

        [Profile Detection]
        os_id = custom-os
        variant_id = custom-variant
        """)
        self._load_profile(content)

        self._check_detection(None, None, None)
        self._check_detection(None, "", "")
        self._check_detection(None, "", "another-variant")
        self._check_detection(None, "", "custom-variant")
        self._check_detection(None, "another-os", "custom-variant")
        self._check_detection("custom-profile", "custom-os", "")
        self._check_detection("custom-profile", "custom-os", None)
        self._check_detection("custom-profile", "custom-os", "another-variant")
        self._check_detection("another-profile", "custom-os", "custom-variant")

    def test_invalid_profile(self):
        with pytest.raises(ConfigurationError):
            self._load_profile("")

        with pytest.raises(ConfigurationError):
            self._load_profile("[Profile]")

        with pytest.raises(ConfigurationError):
            self._load_profile("[Profile Detection]")

        content = dedent("""
        [Profile]
        base_profile = custom-profile
        """)

        with pytest.raises(ConfigurationError):
            self._load_profile(content)

    def test_invalid_base_profile(self):
        content = dedent("""
        [Profile]
        profile_id = custom-profile
        base_profile = nonexistent-profile
        """)
        self._load_profile(content)

        with pytest.raises(ConfigurationError):
            self._loader.collect_configurations("custom-profile")

        assert not self._loader.check_profile("custom-profile")

    def test_repeated_base_profile(self):
        content = dedent("""
        [Profile]
        profile_id = custom-profile
        base_profile = custom-profile
        """)
        self._load_profile(content)

        with pytest.raises(ConfigurationError):
            self._loader.collect_configurations("custom-profile")

        assert not self._loader.check_profile("custom-profile")

    def test_existing_profile(self):
        content = dedent("""
        [Profile]
        profile_id = custom-profile
        """)

        self._load_profile(content)

        with pytest.raises(ConfigurationError):
            self._load_profile(content)

    def test_find_nonexistent_profile(self):
        assert self._loader.check_profile("custom-profile") is False
        assert self._loader.detect_profile("custom-os", "custom-variant") is None

    def test_ignore_invalid_profile(self):
        with tempfile.TemporaryDirectory() as config_dir:

            # A correct profile config.
            with open(os.path.join(config_dir, "1.conf"), "w") as f:
                f.write(dedent("""
                [Profile]
                profile_id = custom-profile-1
                """))

            # An invalid profile config.
            with open(os.path.join(config_dir, "2.conf"), "w") as f:
                f.write("")

            # A profile config with wrong file name.
            with open(os.path.join(config_dir, "3"), "w") as f:
                f.write(dedent("""
                [Profile]
                profile_id = custom-profile-3
                """))

            self._loader.load_profiles(config_dir)
            assert self._loader.check_profile("custom-profile-1")
            assert not self._loader.check_profile("custom-profile-2")
            assert not self._loader.check_profile("custom-profile-3")
