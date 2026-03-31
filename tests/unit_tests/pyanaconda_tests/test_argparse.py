# vim:set fileencoding=utf-8
#
# Copyright (C) 2015  Red Hat, Inc.
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
import unittest

import pytest

from pyanaconda import argument_parsing
from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.constants import DisplayModes
from pyanaconda.core.kernel import KernelArguments


class ArgparseTest(unittest.TestCase):
    def _parseCmdline(self, argv=None, boot_cmdline=None):
        ap = argument_parsing.getArgumentParser("", boot_cmdline)
        return ap.parse_args(argv, boot_cmdline=boot_cmdline)

    def test_without_inst_prefix(self):
        boot_cmdline = KernelArguments.from_string("stage2=http://cool.server.com/test")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 is None

        boot_cmdline = KernelArguments.from_string("stage2=http://cool.server.com/test "
                                                   "rdp")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 is None
        assert not opts.rdp_enabled

    def test_with_inst_prefix(self):
        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"

        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test "
                                                   "inst.rdp")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"
        assert opts.rdp_enabled

    def test_inst_prefix_mixed(self):
        boot_cmdline = KernelArguments.from_string("inst.stage2=http://cool.server.com/test "
                                                   "rdp")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.stage2 == "http://cool.server.com/test"
        assert not opts.rdp_enabled

    def test_display_mode(self):
        opts = self._parseCmdline(['--cmdline'])
        assert opts.display_mode == DisplayModes.TUI
        assert opts.noninteractive

        opts = self._parseCmdline(['--graphical'])
        assert opts.display_mode == DisplayModes.GUI
        assert not opts.noninteractive

        opts = self._parseCmdline(['--text'])
        assert opts.display_mode == DisplayModes.TUI
        assert not opts.noninteractive

        opts = self._parseCmdline(['--noninteractive'])
        assert opts.noninteractive

        opts = self._parseCmdline(['--pauseatsummary'])
        assert opts.pause_at_summary is True

        # Test the default
        opts = self._parseCmdline([])
        assert opts.display_mode == DisplayModes.GUI
        assert not opts.noninteractive

        # console=whatever in the boot args defaults to --text
        boot_cmdline = KernelArguments.from_string("console=/dev/ttyS0")
        opts = self._parseCmdline([], boot_cmdline=boot_cmdline)
        assert opts.display_mode == DisplayModes.TUI

    def test_selinux(self):
        from pykickstart.constants import SELINUX_DISABLED, SELINUX_ENFORCING

        from pyanaconda.core.constants import SELINUX_DEFAULT

        # with no arguments, use SELINUX_DEFAULT
        opts = self._parseCmdline([])
        assert opts.selinux == SELINUX_DEFAULT

        # --selinux or --selinux=1 means SELINUX_ENFORCING
        opts = self._parseCmdline(['--selinux'])
        assert opts.selinux == SELINUX_ENFORCING

        # --selinux=0 means SELINUX_DISABLED
        opts = self._parseCmdline(['--selinux=0'])
        assert opts.selinux == SELINUX_DISABLED

        # --noselinux means SELINUX_DISABLED
        opts = self._parseCmdline(['--noselinux'])
        assert opts.selinux == SELINUX_DISABLED

    def test_dirinstall(self):
        # when not specified, dirinstall should evaluate to False
        opts = self._parseCmdline([])
        assert not opts.dirinstall

        # with no argument, dirinstall should default to /mnt/sysimage
        opts = self._parseCmdline(['--dirinstall'])
        assert opts.dirinstall == "/mnt/sysimage"

        # with an argument, dirinstall should use that
        opts = self._parseCmdline(['--dirinstall=/what/ever'])
        assert opts.dirinstall == "/what/ever"

    def test_storage(self):
        conf = AnacondaConfiguration.from_defaults()

        opts = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.storage.ibft is True

        opts = self._parseCmdline(['--ibft'])
        conf.set_from_opts(opts)

        assert conf.storage.ibft is True

    def test_target(self):
        conf = AnacondaConfiguration.from_defaults()

        opts = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is True
        assert conf.target.is_image is False
        assert conf.target.is_directory is False
        assert conf.target.physical_root == "/mnt/sysimage"

        opts = self._parseCmdline(['--image=/what/ever.img'])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is False
        assert conf.target.is_image is True
        assert conf.target.is_directory is False
        assert conf.target.physical_root == "/mnt/sysimage"

        opts = self._parseCmdline(['--dirinstall=/what/ever'])
        conf.set_from_opts(opts)

        assert conf.target.is_hardware is False
        assert conf.target.is_image is False
        assert conf.target.is_directory is True
        assert conf.target.physical_root == "/what/ever"

    def test_target_nosave(self):
        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is True
        assert conf.target.can_save_installation_logs is True
        assert conf.target.can_save_output_kickstart is True

        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline(['--nosave=all'])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is False
        assert conf.target.can_save_installation_logs is False
        assert conf.target.can_save_output_kickstart is False

        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline(['--nosave=all_ks'])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is False
        assert conf.target.can_save_installation_logs is True
        assert conf.target.can_save_output_kickstart is False

        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline(['--nosave=logs'])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is True
        assert conf.target.can_save_installation_logs is False
        assert conf.target.can_save_output_kickstart is True

        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline(['--nosave=input_ks'])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is False
        assert conf.target.can_save_installation_logs is True
        assert conf.target.can_save_output_kickstart is True

        conf = AnacondaConfiguration.from_defaults()
        opts = self._parseCmdline(['--nosave=output_ks'])
        conf.set_from_opts(opts)

        assert conf.target.can_copy_input_kickstart is True
        assert conf.target.can_save_installation_logs is True
        assert conf.target.can_save_output_kickstart is False

    def test_system(self):
        conf = AnacondaConfiguration.from_defaults()

        opts = self._parseCmdline([])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is True
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is False

        opts = self._parseCmdline(['--liveinst'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is True
        assert conf.system._is_unknown is False

        opts = self._parseCmdline(['--dirinstall=/what/ever'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is True

        opts = self._parseCmdline(['--image=/what/ever.img'])
        conf.set_from_opts(opts)

        assert conf.system._is_boot_iso is False
        assert conf.system._is_live_os is False
        assert conf.system._is_unknown is True

    def test_addrepo(self):
        # Test invalid options.
        with pytest.raises(ValueError):
            self._parseCmdline(["--addrepo=r1"])

        with pytest.raises(ValueError):
            self._parseCmdline(["--addrepo=http://url/1"])

        # Test cmdline options.
        opts = self._parseCmdline([
            "--addrepo=r1,http://url/1"
        ])
        assert opts.addRepo == [
            ("r1", "http://url/1")
        ]

        opts = self._parseCmdline([
            "--addrepo=r1,http://url/1",
            "--addrepo=r2,http://url/2",
            "--addrepo=r3,http://url/3",
        ])
        assert opts.addRepo == [
            ("r1", "http://url/1"),
            ("r2", "http://url/2"),
            ("r3", "http://url/3"),
        ]

        # Test invalid boot options.
        boot_cmdline = KernelArguments.from_string(
            "inst.addrepo=r1"
        )
        with pytest.raises(ValueError) as cm:
            self._parseCmdline([], boot_cmdline)

        expected = \
            "The addrepo option has incorrect format ('r1'). " \
            "Use: inst.addrepo=<name>,<url>"

        assert str(cm.value) == expected

        boot_cmdline = KernelArguments.from_string(
            "inst.addrepo=http://url/1"
        )
        with pytest.raises(ValueError):
            self._parseCmdline([], boot_cmdline)

        # Test boot options.
        boot_cmdline = KernelArguments.from_string(
            "inst.addrepo=r1,http://url/1"
        )
        opts = self._parseCmdline([], boot_cmdline)
        assert opts.addRepo == [
            ("r1", "http://url/1")
        ]

        boot_cmdline = KernelArguments.from_string(
            "inst.addrepo=r1,http://url/1 "
            "inst.addrepo=r2,http://url/2 "
            "inst.addrepo=r3,http://url/3 "
        )
        opts = self._parseCmdline([], boot_cmdline)
        assert opts.addRepo == [
            ("r1", "http://url/1"),
            ("r2", "http://url/2"),
            ("r3", "http://url/3"),
        ]


# Pytest-style tests for remote-debugger argument parsing
class RemoteDebuggerArgumentTest:
    """Tests for the --remote-debugger argument parser."""

    @pytest.fixture
    def arg_parser(self):
        """Fixture that provides an argument parser instance."""
        return argument_parsing.getArgumentParser("")

    @pytest.fixture
    def dbus_services_path(self, tmp_path, monkeypatch):
        # Monkeypatch the ANACONDA_DATADIR environment variable
        monkeypatch.setenv("ANACONDA_DATADIR", str(tmp_path))
        # Create a fake dbus directory for service files
        dbus_dir = tmp_path / "dbus"
        dbus_dir.mkdir()
        return dbus_dir

    def test_remote_debugger_default_value(self, arg_parser):
        """Test that --remote-debugger defaults to empty dict when not specified."""
        opts = arg_parser.parse_args([])
        assert opts.remote_debugger is None

    def test_remote_debugger_single_module(self, arg_parser):
        """Test --remote-debugger with a single module:port specification."""
        opts = arg_parser.parse_args(["--remote-debugger", "anaconda:50000"])
        assert opts.remote_debugger == {"anaconda": 50000}

    def test_remote_debugger_multiple_modules(self, arg_parser):
        """Test --remote-debugger with multiple module:port specifications."""
        opts = arg_parser.parse_args(
            [
                "--remote-debugger",
                "anaconda:50000",
                "--remote-debugger",
                "pyanaconda.modules.boss:50001",
                "--remote-debugger",
                "pyanaconda.modules.network:50002",
            ]
        )
        assert opts.remote_debugger == {
            "anaconda": 50000,
            "pyanaconda.modules.boss": 50001,
            "pyanaconda.modules.network": 50002,
        }

    def test_remote_debugger_invalid_format_no_colon(self, arg_parser):
        """Test --remote-debugger with invalid format (missing colon)."""
        with pytest.raises(ValueError) as cm:
            arg_parser.parse_args(["--remote-debugger", "anaconda"])
        assert "Invalid remote-debugger format" in str(cm.value)

    def test_remote_debugger_invalid_all_format(self, arg_parser):
        """Test --remote-debugger all with invalid format (no range)."""
        with pytest.raises(ValueError) as cm:
            arg_parser.parse_args(["--remote-debugger", "all:50000"])
        assert "Invalid 'all' format" in str(cm.value)

    def test_remote_debugger_all_modules(self, dbus_services_path):
        """Test --remote-debugger all:start-end with dynamically discovered modules."""

        # Create mock service files
        service_files = [
            ("org.fedoraproject.Anaconda.ServiceC.service", "pyanaconda.modules.service_c"),
            ("org.fedoraproject.Anaconda.ServiceB.service", "pyanaconda.modules.service_b"),
            ("org.fedoraproject.Anaconda.ServiceA.service", "pyanaconda.modules.service_a"),
        ]

        for filename, module_name in service_files:
            service_file = dbus_services_path / filename
            service_file.write_text(
                f"[D-BUS Service]\n"
                f"Name=org.fedoraproject.Anaconda\n"
                f"Exec=/usr/bin/anaconda-start-module {module_name}\n"
            )

        ap = argument_parsing.getArgumentParser("")
        opts = ap.parse_args(["--remote-debugger", "all:50000-50020"])

        # anaconda gets port 50000, then modules in sorted order
        assert opts.remote_debugger == {
            "anaconda": 50000,
            "pyanaconda.modules.service_a": 50001,
            "pyanaconda.modules.service_b": 50002,
            "pyanaconda.modules.service_c": 50003,
        }

    def test_remote_debugger_all_end_port_validated(self, dbus_services_path):
        """Test --remote-debugger all rejects a range too small for all modules."""
        for name, mod in [
            ("org.fedoraproject.Anaconda.A.service", "pyanaconda.modules.a"),
            ("org.fedoraproject.Anaconda.B.service", "pyanaconda.modules.b"),
            ("org.fedoraproject.Anaconda.C.service", "pyanaconda.modules.c"),
        ]:
            (dbus_services_path / name).write_text(
                f"[D-BUS Service]\nExec=/usr/bin/anaconda-start-module {mod}\n"
            )

        ap = argument_parsing.getArgumentParser("")

        # 4 ports needed (anaconda + 3 modules), but range 50000-50002 provides only 3
        with pytest.raises(ValueError) as cm:
            ap.parse_args(["--remote-debugger", "all:50000-50002"])

        error_msg = str(cm.value)
        assert "provides 3 ports" in error_msg
        assert "4 are needed" in error_msg

    def test_remote_debugger_all_exact_range(self, dbus_services_path):
        """Test --remote-debugger all succeeds when range exactly fits all modules."""
        for name, mod in [
            ("org.fedoraproject.Anaconda.A.service", "pyanaconda.modules.a"),
            ("org.fedoraproject.Anaconda.B.service", "pyanaconda.modules.b"),
        ]:
            (dbus_services_path / name).write_text(
                f"[D-BUS Service]\nExec=/usr/bin/anaconda-start-module {mod}\n"
            )

        ap = argument_parsing.getArgumentParser("")

        # 3 ports needed (anaconda + 2 modules), range 50000-50002 provides exactly 3
        opts = ap.parse_args(["--remote-debugger", "all:50000-50002"])
        assert opts.remote_debugger == {
            "anaconda": 50000,
            "pyanaconda.modules.a": 50001,
            "pyanaconda.modules.b": 50002,
        }

    def test_remote_debugger_all_end_port_less_than_start(self, arg_parser):
        """Test --remote-debugger all rejects end port less than start port."""
        with pytest.raises(ValueError) as cm:
            arg_parser.parse_args(["--remote-debugger", "all:50020-50000"])
        assert "must be greater than start port" in str(cm.value)

    def test_remote_debugger_all_equal_ports(self, arg_parser):
        """Test --remote-debugger all rejects equal start and end ports."""
        with pytest.raises(ValueError) as cm:
            arg_parser.parse_args(["--remote-debugger", "all:50000-50000"])
        assert "must be greater than start port" in str(cm.value)

    def test_remote_debugger_all_modules_no_files(self, dbus_services_path):
        """Test --remote-debugger all when no service files exist."""
        ap = argument_parsing.getArgumentParser("")
        opts = ap.parse_args(["--remote-debugger", "all:50000-50020"])

        # Only anaconda should be configured when no modules are found
        assert opts.remote_debugger == {"anaconda": 50000}

    def test_remote_debugger_all_malformed_service_file(self, dbus_services_path):
        """Test --remote-debugger all with malformed service files."""
        service_file = dbus_services_path / "org.fedoraproject.Anaconda.Boss.service"
        service_file.write_text("[D-BUS Service]\nName=org.fedoraproject.Anaconda\n")

        ap = argument_parsing.getArgumentParser("")
        opts = ap.parse_args(["--remote-debugger", "all:50000-50020"])

        # Should still work but only configure anaconda
        assert opts.remote_debugger == {"anaconda": 50000}

    def test_remote_debugger_all_file_read_error(self, dbus_services_path):
        """Test --remote-debugger all when service files can't be read (OSError)."""
        service_path = dbus_services_path / "org.fedoraproject.Anaconda.Some.service"
        service_path.mkdir()

        ap = argument_parsing.getArgumentParser("")

        with pytest.raises(ValueError) as cm:
            ap.parse_args(["--remote-debugger", "all:50000-50020"])

        error_msg = str(cm.value)
        assert "Failed to read service files" in error_msg
        assert "org.fedoraproject.Anaconda.Some.service" in error_msg

    def test_remote_debugger_mixed_usage_specific_then_all(self, arg_parser):
        """Test that mixing specific modules with 'all' raises an error (specific first)."""
        with pytest.raises(ValueError) as cm:
            arg_parser.parse_args(
                ["--remote-debugger", "custom.module:49999", "--remote-debugger", "all:50000-50020"]
            )

        error_msg = str(cm.value)
        assert "Cannot use 'all' with specific module configurations" in error_msg

    def test_remote_debugger_mixed_usage_all_then_specific(self, dbus_services_path):
        """Test that mixing 'all' with specific modules raises an error (all first)."""
        service_file = dbus_services_path / "org.fedoraproject.Anaconda.Boss.service"
        service_file.write_text(
            "[D-BUS Service]\n"
            "Name=org.fedoraproject.Anaconda\n"
            "Exec=/usr/bin/anaconda-start-module pyanaconda.modules.boss\n"
        )

        ap = argument_parsing.getArgumentParser("")
        with pytest.raises(ValueError) as cm:
            ap.parse_args(["--remote-debugger", "all:50000-50020", "--remote-debugger", "custom.module:49999"])

        error_msg = str(cm.value)
        assert "Cannot use specific module configurations with 'all'" in error_msg

    def test_remote_debugger_boot_cmdline(self):
        """Test --remote-debugger via boot command line."""
        boot_cmdline = KernelArguments.from_string("inst.remote-debugger=anaconda:50000")
        ap = argument_parsing.getArgumentParser("", boot_cmdline)
        opts = ap.parse_args([], boot_cmdline=boot_cmdline)
        assert opts.remote_debugger == {"anaconda": 50000}

    def test_remote_debugger_boot_cmdline_multiple(self):
        """Test multiple --remote-debugger via boot command line."""
        boot_cmdline = KernelArguments.from_string(
            "inst.remote-debugger=anaconda:50000 inst.remote-debugger=pyanaconda.modules.boss:50001"
        )
        ap = argument_parsing.getArgumentParser("", boot_cmdline)
        opts = ap.parse_args([], boot_cmdline=boot_cmdline)
        assert opts.remote_debugger == {"anaconda": 50000, "pyanaconda.modules.boss": 50001}
