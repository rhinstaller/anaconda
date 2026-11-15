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
from datetime import datetime, timezone
from shutil import copyfile, copytree
from unittest.mock import call, create_autospec, patch

import pytest

from pyanaconda.core.constants import TIME_SOURCE_POOL, TIME_SOURCE_SERVER
from pyanaconda.modules.common.errors.installation import TimezoneConfigurationError
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.timezone.installation import (
    ChronyUnavailable,
    ConfigureHardwareClockTask,
    ConfigureNTPTask,
    ConfigureTimezoneTask,
    RTCHeuristicTask,
)
from pyanaconda.modules.timezone.timezone import TimezoneService
from pyanaconda.ntp import NTP_CONFIG_FILE, NTPconfigError


class TimezoneTasksTestCase(unittest.TestCase):
    """Test the D-Bus Timezone (Timezone only) tasks."""

    def test_timezone_task_success(self):
        """Test the "full success" code paths in timezone D-Bus task."""
        self._test_timezone_inputs(
            input_zone="Europe/Prague",
            input_isutc=False,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/Europe/Prague",
            expected_adjtime_last_line="LOCAL"
        )
        self._test_timezone_inputs(
            input_zone="Africa/Bissau",
            input_isutc=True,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/Africa/Bissau",
            expected_adjtime_last_line="UTC"
        )
        self._test_timezone_inputs(
            input_zone="Etc/GMT-12",
            input_isutc=True,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/Etc/GMT-12",
            expected_adjtime_last_line="UTC"
        )
        self._test_timezone_inputs(
            input_zone="Etc/GMT+3",
            input_isutc=True,
            make_adjtime=False,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/Etc/GMT+3",
            expected_adjtime_last_line="UTC"
        )

    def test_timezone_task_correction(self):
        """Test nonsensical time zone correction in timezone D-Bus task."""
        self._test_timezone_inputs(
            input_zone="",
            input_isutc=True,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/America/New_York",
            expected_adjtime_last_line="UTC"
        )
        self._test_timezone_inputs(
            input_zone="BahBlah",
            input_isutc=True,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/America/New_York",
            expected_adjtime_last_line="UTC"
        )
        self._test_timezone_inputs(
            input_zone=None,
            input_isutc=True,
            make_adjtime=True,
            make_zoneinfo=True,
            expected_symlink="../usr/share/zoneinfo/America/New_York",
            expected_adjtime_last_line="UTC"
        )

    @patch('pyanaconda.modules.timezone.installation.arch.is_s390', return_value=True)
    def test_timezone_task_s390(self, mock_is_s390):
        """Test skipping writing /etc/adjtime on s390"""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            self._execute_task(sysroot, "Africa/Bissau", False)
            self._check_timezone_symlink(sysroot, "../usr/share/zoneinfo/Africa/Bissau")
            assert not os.path.exists(sysroot + "/etc/adjtime")
        mock_is_s390.assert_called_once()
        # expected state: calling it only once in the check for architecture

    def test_timezone_task_timezone_missing(self):
        """Test failure when setting a valid but missing timezone."""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            os.remove(sysroot + "/usr/share/zoneinfo/Asia/Ulaanbaatar")
            with self.assertLogs("anaconda.modules.timezone.installation", level="ERROR"):
                self._execute_task(sysroot, "Asia/Ulaanbaatar", False)
            assert not os.path.exists(sysroot + "/etc/localtime")

    @patch("pyanaconda.modules.timezone.installation.os.symlink", side_effect=OSError)
    def test_timezone_task_symlink_failure(self, mock_os_symlink):
        """Test failure when symlinking the time zone."""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            with self.assertLogs("anaconda.modules.timezone.installation", level="ERROR"):
                self._execute_task(sysroot, "Asia/Ulaanbaatar", False)
            assert not os.path.exists(sysroot + "/etc/localtime")

    @patch('pyanaconda.modules.timezone.installation.open', side_effect=OSError)
    def test_timezone_task_write_adjtime_failure(self, mock_open):
        """Test failure when writing the /etc/adjtime file."""
        # Note the first open() in the target code should not fail due to mocking, but it would
        # anyway due to /etc/adjtime missing from env. setup, so it's ok if it does.
        with tempfile.TemporaryDirectory() as sysroot:
            with pytest.raises(TimezoneConfigurationError):
                self._setup_environment(sysroot, False, True)
                self._execute_task(sysroot, "Atlantic/Faroe", False)
            assert not os.path.exists(sysroot + "/etc/adjtime")
            assert os.path.exists(sysroot + "/etc/localtime")

    def _test_timezone_inputs(self, input_zone, input_isutc, make_adjtime, make_zoneinfo,
                              expected_symlink, expected_adjtime_last_line):
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, make_adjtime, make_zoneinfo)
            self._execute_task(sysroot, input_zone, input_isutc)
            self._check_timezone_symlink(sysroot, expected_symlink)
            self._check_utc_lastline(sysroot, expected_adjtime_last_line)

    def _setup_environment(self, sysroot, make_adjtime, make_zoneinfo):
        os.mkdir(sysroot + "/etc")
        if make_adjtime:
            copyfile("/etc/adjtime", sysroot + "/etc/adjtime")
        if make_zoneinfo:
            copytree("/usr/share/zoneinfo", sysroot + "/usr/share/zoneinfo")

    def _execute_task(self, sysroot, tz, is_utc):
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.timezone = tz
        service.is_utc = is_utc
        service.set_timezone.side_effect = lambda value: setattr(service, "timezone", value)

        task = ConfigureTimezoneTask(
            sysroot=sysroot,
            timezone_service=service,
        )
        task.run()

    def _check_timezone_symlink(self, sysroot, expected_symlink):
        """Check if the right timezone is set as the symlink."""
        link_target = os.readlink(sysroot + "/etc/localtime")
        assert expected_symlink == link_target

    def _check_utc_lastline(self, sysroot, expected_adjtime_last_line):
        """Check that the UTC was saved"""
        with open(os.path.normpath(sysroot + "/etc/adjtime"), "r") as fobj:
            # Careful, this can die on huge files accidentally stuffed there instead.
            lines = fobj.readlines()
            # It must be last line because we write it so and nothing should have touched
            # it in test environment.
            last_line = lines[-1].strip()
            assert expected_adjtime_last_line == last_line


class NTPTasksTestCase(unittest.TestCase):
    """Test the D-Bus NTP tasks from the Timezone module."""

    def test_ntp_task_success(self):
        """Test the success cases for NTP setup D-Bus task."""
        self._test_ntp_inputs(
            make_chronyd=False,
            ntp_enabled=False
        )
        self._test_ntp_inputs(
            make_chronyd=False,
            ntp_enabled=True
        )

    def test_ntp_overwrite(self):
        """Test overwriting existing config for NTP setup D-Bus task."""
        self._test_ntp_inputs(
            make_chronyd=True,
            ntp_enabled=True
        )
        self._test_ntp_inputs(
            make_chronyd=True,
            ntp_enabled=False
        )

    def test_ntp_service(self):
        """Test enabling of the NTP service in a D-Bus task."""
        self._test_ntp_inputs(
            ntp_enabled=False,
            ntp_installed=True
        )
        self._test_ntp_inputs(
            ntp_enabled=True,
            ntp_installed=True
        )

    @patch("pyanaconda.modules.timezone.installation.ntp.save_servers_to_config")
    def test_ntp_save_failure(self, save_servers):
        """Test failure when saving NTP config in D-Bus task."""
        save_servers.side_effect = NTPconfigError

        with self.assertLogs("anaconda.modules.timezone.installation", level="WARNING"):
            self._test_ntp_inputs(
                make_chronyd=True,
                ntp_enabled=True,
                ntp_config_error=True
            )

        with self.assertLogs("anaconda.modules.timezone.installation", level="WARNING"):
            self._test_ntp_inputs(
                make_chronyd=False,
                ntp_enabled=True,
                ntp_config_error=True
            )

        save_servers.assert_called()

    def _get_test_sources(self):
        """Get a list of sources"""
        server = TimeSourceData()
        server.type = TIME_SOURCE_SERVER
        server.hostname = "unique.ntp.server"
        server.options = ["iburst"]

        pool = TimeSourceData()
        pool.type = TIME_SOURCE_POOL
        pool.hostname = "another.unique.server"

        return [server, pool]

    def _get_expected_lines(self):
        return [
            "server unique.ntp.server iburst\n",
            "pool another.unique.server\n"
        ]

    def _test_ntp_inputs(self, make_chronyd=False, ntp_enabled=True, ntp_installed=False,
                         ntp_config_error=False):
        ntp_servers = self._get_test_sources()
        expected_lines = self._get_expected_lines()

        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, make_chronyd)

            with patch("pyanaconda.modules.timezone.installation.service") as service_util:
                service_util.is_service_installed.return_value = ntp_installed
                self._execute_task(sysroot, ntp_enabled, ntp_servers)
                self._validate_ntp_service(sysroot, service_util, ntp_installed, ntp_enabled)

            if ntp_config_error:
                return

            self._validate_ntp_config(sysroot, make_chronyd, ntp_enabled, expected_lines)

    def _setup_environment(self, sysroot, make_chronyd):
        os.mkdir(sysroot + "/etc")
        if make_chronyd:
            copyfile(NTP_CONFIG_FILE, sysroot + NTP_CONFIG_FILE)

    def _execute_task(self, sysroot, ntp_enabled, ntp_servers):
        task = ConfigureNTPTask(
            sysroot=sysroot,
            ntp_enabled=ntp_enabled,
            ntp_servers=ntp_servers
        )
        task.run()

    def _validate_ntp_service(self, sysroot, service_util, ntp_installed, ntp_enabled):
        service_util.is_service_installed.assert_called_once_with(
            "chronyd", root=sysroot
        )

        if not ntp_installed:
            service_util.enable_service.assert_not_called()
            service_util.disable_service.assert_not_called()
        elif ntp_enabled:
            service_util.enable_service.assert_called_once_with(
                "chronyd", root=sysroot
            )
            service_util.disable_service.assert_not_called()
        else:
            service_util.enable_service.assert_not_called()
            service_util.disable_service.assert_called_once_with(
                "chronyd", root=sysroot
            )

    def _validate_ntp_config(self, sysroot, was_present, was_enabled, expected_lines):
        if was_enabled:
            with open(sysroot + NTP_CONFIG_FILE) as fobj:
                all_lines = fobj.readlines()

            for line in expected_lines:
                assert line in all_lines

        elif not was_present:
            assert not os.path.exists(sysroot + NTP_CONFIG_FILE)


class TimezoneHardwareClockTasksTestCase(unittest.TestCase):
    """Test the D-Bus Timezone Hardware Clock task."""

    @patch("pyanaconda.modules.timezone.installation.util.execWithRedirect")
    @patch('pyanaconda.modules.timezone.installation.arch.is_s390', return_value=True)
    def test_hwclock_config_task_s390(self, mock_is_s390, mock_exec_with_redirect):
        """Test that save_hw_clock does nothing on s390."""
        self._execute_task(False)
        # expected state: calling it only once in the check for architecture
        mock_is_s390.assert_called_once()
        mock_exec_with_redirect.assert_not_called()

    @patch("pyanaconda.modules.timezone.installation.util.execWithRedirect")
    def test_hwclock_config_task_disabled(self, mock_exec_with_redirect):
        """Test the Hardware clock configuration task - can't setup hardware clock"""
        with patch("pyanaconda.modules.timezone.installation.conf") as mock_conf:
            mock_conf.system.can_set_hardware_clock = False
            self._execute_task(True)
            mock_exec_with_redirect.assert_not_called()

    @patch("pyanaconda.modules.timezone.installation.util.execWithRedirect")
    def test_hwclock_config_task_local(self, mock_exec_with_redirect):
        """Test the Hardware clock configuration task - local"""
        with patch("pyanaconda.modules.timezone.installation.conf") as mock_conf:
            mock_conf.system.can_set_hardware_clock = True
            self._execute_task(False)
            mock_exec_with_redirect.assert_called_once_with(
                'hwclock',
                ['--systohc', '--local']
            )

    @patch("pyanaconda.modules.timezone.installation.util.execWithRedirect")
    def test_hwclock_config_task_utc(self, mock_exec_with_redirect):
        """Test the Hardware clock configuration task - utc"""
        with patch("pyanaconda.modules.timezone.installation.conf") as mock_conf:
            mock_conf.system.can_set_hardware_clock = True
            self._execute_task(True)
            mock_exec_with_redirect.assert_called_once_with(
                'hwclock',
                ['--systohc', '--utc']
            )

    def _execute_task(self, is_utc):
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.is_utc = is_utc
        task = ConfigureHardwareClockTask(
            timezone_service=service,
        )
        task.run()

    @patch("pyanaconda.modules.timezone.installation.util.execWithRedirect")
    def test_is_utc_propagation(self, mock_exec):
        """Test that updates to IsUTC from earlier tasks are used by ConfigureHardwareClockTask."""

        # Pretend we've discovered an NTFS partition
        service = TimezoneService()
        service.set_is_utc(False)

        tasks = service.install_with_tasks()
        task = next(t for t in tasks if isinstance(t, ConfigureHardwareClockTask))
        assert service.is_utc is False

        # After task generation, the heuristic task updates is_utc
        service.set_is_utc(True)

        with patch("pyanaconda.modules.timezone.installation.conf") as mock_conf:
            mock_conf.system.can_set_hardware_clock = True
            task.run()
            # And we use the updated value
            mock_exec.assert_called_once_with('hwclock', ['--systohc', '--utc'])

class TimezoneRTCHeuristicTasksTestCase(unittest.TestCase):
    def test_run_no_heuristic(self):
        """Test that in non-heuristic mode, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = False
        service.timezone = None
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T18:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_run_no_ntp_time(self):
        """Test that with no NTP time available, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = 'America/New_York'
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T18:20:00")), \
            patch.object(task, "_chrony_utc", return_value=None):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_run_no_rtc_time(self):
        """Test that with no RTC time available, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = 'America/New_York'
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=None), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_run_no_timezone(self):
        """Test that with no timezone available, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = None
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T18:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_run_bad_tz(self):
        """Test that with a bad timezone, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = "Not/Real"
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T18:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    @patch('pyanaconda.modules.timezone.installation.util.execProgram')
    def test_run_choose_local(self, mock_exec):
        """Test that if RTC time matches local time, run selects local time."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = "America/New_York"
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T18:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_called_once_with(False)
        mock_exec.assert_called_once_with('hwclock', ['--hctosys', '--local'])

    @patch('pyanaconda.modules.timezone.installation.util.execProgram')
    def test_run_choose_utc(self, mock_exec):
        """Test that if RTC time matches UTC time, run selects UTC time."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = "America/New_York"
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T23:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_called_once_with(True)
        mock_exec.assert_called_once_with('hwclock', ['--hctosys', '--utc'])

    def test_run_no_match(self):
        """Test that if RTC time matches neither local nor UTC time, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = "America/New_York"
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T22:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_run_both_match(self):
        """Test that if RTC time matches both local and UTC time, run does nothing."""
        service = create_autospec(TimezoneService, spec_set=True, instance=True)
        service.rtc_heuristic = True
        service.timezone = "Europe/London"
        task = RTCHeuristicTask(timezone_service=service)
        with patch.object(task, "_read_rtc", return_value=datetime.fromisoformat("2026-11-15T23:20:00")), \
            patch.object(task, "_chrony_utc", return_value=datetime.fromisoformat("2026-11-15T23:21:10+0000")):
            task.run()
        service.set_is_utc.assert_not_called()

    def test_read_rtc(self):
        """Test that reading from the RTC calls hwclock correctly."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock:
            mock.return_value = (0, "2026-11-16 00:47:44.898808+00:00\n")
            ret = task._read_rtc()
            assert ret == datetime.fromisoformat("2026-11-16 00:47:44.898808+00:00")
            mock.assert_called_once_with('hwclock', ['--show', '--utc'], env_add={"TZ": "UTC0"})

    def test_read_rtc_fail(self):
        """Test that reading from the RTC just returns None on failure."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock:
            mock.return_value = (-1, "")
            ret = task._read_rtc()
            assert ret is None
            mock.assert_called_once_with('hwclock', ['--show', '--utc'], env_add={"TZ": "UTC0"})

    def test_chrony_utc_once_slow(self):
        """Test that if chrony finds the sysclock is slow, _chrony_utc_once calculates UTC correctly."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec, \
            patch('pyanaconda.modules.timezone.installation.datetime') as mock_datetime:
            mock_exec.return_value = (0, "CE6C0083,206.108.0.131,2,1794790582.575424911,9351.443359375,-0.000001402,965.307922363,3.459,-0.004,0.862,0.027274847,0.000706511,129.2,Normal\n")
            mock_datetime.now.return_value = datetime.fromisoformat("2026-11-15T22:23:30+0000")
            ret = task._chrony_utc_once()
            assert ret == datetime.fromisoformat("2026-11-16T00:59:21.443359375+0000")
            mock_exec.assert_called_once_with('chronyc', ['-c', 'tracking'])

    def test_chrony_utc_once_fast(self):
        """Test that if chrony finds the sysclock is fast, _chrony_utc_once calculates UTC correctly."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec, \
            patch('pyanaconda.modules.timezone.installation.datetime') as mock_datetime:
            mock_exec.return_value = (0, "CE6C0083,206.108.0.131,2,1794790582.575424911,-10.3,-0.000001402,965.307922363,3.459,-0.004,0.862,0.027274847,0.000706511,129.2,Normal\n")
            mock_datetime.now.return_value = datetime.fromisoformat("2026-11-15T22:23:30+0000")
            ret = task._chrony_utc_once()
            assert ret == datetime.fromisoformat("2026-11-15T22:23:19.7+0000")
            mock_exec.assert_called_once_with('chronyc', ['-c', 'tracking'])

    def test_chrony_utc_once_unsynced(self):
        """Test that if chrony is unsynced, _chrony_utc_once returns None."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec:
            mock_exec.return_value = (0, "CE6C0083,206.108.0.131,2,1794790582.575424911,-10.3,-0.000001402,965.307922363,3.459,-0.004,0.862,0.027274847,0.000706511,129.2,Not synchronised\n")
            ret = task._chrony_utc_once()
            assert ret is None
            mock_exec.assert_called_once_with('chronyc', ['-c', 'tracking'])

    def test_chrony_utc_once_no_chrony(self):
        """Test that if chrony isn't running _chrony_utc_once raises an exception."""
        task = RTCHeuristicTask(None)
        with patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec:
            mock_exec.return_value = (-1, "")
            with self.assertRaises(ChronyUnavailable):
                task._chrony_utc_once()
            mock_exec.assert_called_once_with('chronyc', ['-c', 'tracking'])

    def test_chrony_utc_synced(self):
        """Test that if chrony is synced, _chrony_utc finds UTC time immediately."""
        task = RTCHeuristicTask(None)
        t = datetime.now(timezone.utc)
        with patch.object(task, "_chrony_utc_once") as mock:
            mock.return_value = t
            assert task._chrony_utc() == t
            mock.assert_called_once()

    def test_chrony_utc_resync(self):
        """Test that if chrony has reset, _chrony_utc tries to make it sync."""
        task = RTCHeuristicTask(None)
        t = datetime.now(timezone.utc)
        with patch.object(task, "_chrony_utc_once") as mock_chrony_utc_once, \
            patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec:
            mock_chrony_utc_once.side_effect = [None, t]
            assert task._chrony_utc() == t
            assert mock_chrony_utc_once.call_count == 2
            assert mock_exec.mock_calls == [
                call('chronyc', ['burst', '3/10']),
                call('chronyc', ['waitsync', '10', '0', '0', '1']),
            ]

    def test_chrony_utc_no_sync(self):
        task = RTCHeuristicTask(None)
        with patch.object(task, "_chrony_utc_once") as mock_chrony_utc_once, \
            patch('pyanaconda.modules.timezone.installation.util.execProgram') as mock_exec:
            mock_chrony_utc_once.side_effect = [None, None]
            assert task._chrony_utc() is None
            assert mock_chrony_utc_once.call_count == 2
            assert mock_exec.mock_calls == [
                call('chronyc', ['burst', '3/10']),
                call('chronyc', ['waitsync', '10', '0', '0', '1']),
            ]

    def test_chrony_utc_no_chrony(self):
        task = RTCHeuristicTask(None)
        with patch.object(task, "_chrony_utc_once") as mock_chrony_utc_once:
            mock_chrony_utc_once.side_effect = ChronyUnavailable
            assert task._chrony_utc() is None
            mock_chrony_utc_once.assert_called_once()
