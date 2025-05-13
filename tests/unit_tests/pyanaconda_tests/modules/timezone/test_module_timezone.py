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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from collections import OrderedDict
from unittest.mock import MagicMock, patch

from dasbus.structure import compare_data
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import (
    TIME_SOURCE_POOL,
    TIME_SOURCE_SERVER,
    TIMEZONE_PRIORITY_DEFAULT,
    TIMEZONE_PRIORITY_GEOLOCATION,
    TIMEZONE_PRIORITY_KICKSTART,
    TIMEZONE_PRIORITY_LANGUAGE,
    TIMEZONE_PRIORITY_USER,
)
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.structures.timezone import (
    GeolocationData,
    TimeSourceData,
)
from pyanaconda.modules.timezone.initialization import GeolocationTask
from pyanaconda.modules.timezone.installation import (
    ConfigureHardwareClockTask,
    ConfigureNTPTask,
    ConfigureTimezoneTask,
)
from pyanaconda.modules.timezone.timezone import TimezoneService
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface
from pyanaconda.timezone import get_timezone
from tests.unit_tests.pyanaconda_tests import (
    check_dbus_property,
    check_kickstart_interface,
    check_task_creation_list,
    patch_dbus_publish_object,
)


class TimezoneInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the timezone module."""

    def setUp(self):
        """Set up the timezone module."""
        # Set up the timezone module.
        self.timezone_module = TimezoneService()
        self.timezone_interface = TimezoneInterface(self.timezone_module)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            TIMEZONE,
            self.timezone_interface,
            *args, **kwargs
        )

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.timezone_interface.KickstartCommands == ["timezone", "timesource"]
        assert self.timezone_interface.KickstartSections == []
        assert self.timezone_interface.KickstartAddons == []

    def test_timezone_property(self):
        """Test the Timezone property."""
        self._check_dbus_property(
            "Timezone",
            "Europe/Prague"
        )

    def test_utc_property(self):
        """Test the IsUtc property."""
        self._check_dbus_property(
            "IsUTC",
            True
        )

    def test_ntp_property(self):
        """Test the NTPEnabled property."""
        self._check_dbus_property(
            "NTPEnabled",
            False
        )

    def test_time_sources_property(self):
        """Test the TimeSources property."""
        server = {
            "type": get_variant(Str, TIME_SOURCE_SERVER),
            "hostname": get_variant(Str, "ntp.cesnet.cz"),
            "options": get_variant(List[Str], ["iburst"]),
        }

        pool = {
            "type": get_variant(Str, TIME_SOURCE_POOL),
            "hostname": get_variant(Str, "0.fedora.pool.ntp.org"),
            "options": get_variant(List[Str], []),
        }

        self._check_dbus_property(
            "TimeSources",
            [server, pool]
        )

    def test_timezone_priority_constants(self):
        """Test the timezone priority constants are in correct order."""
        # assert order of priorities is correct AND nothing equals
        assert TIMEZONE_PRIORITY_DEFAULT \
               < TIMEZONE_PRIORITY_LANGUAGE \
               < TIMEZONE_PRIORITY_GEOLOCATION \
               < TIMEZONE_PRIORITY_KICKSTART \
               < TIMEZONE_PRIORITY_USER

    def test_timezone_priority(self):
        """Test the SetTimezoneWithPriority function."""
        # initialize priority to a low value, which is impossible via the interface as other
        # tests set just Timezone which uses the highest priority
        self.timezone_module._timezone = "Default/Default"
        self.timezone_module._priority = TIMEZONE_PRIORITY_DEFAULT
        assert self.timezone_interface.Timezone == "Default/Default"  # as initialized
        # check higher priority overwrites
        self.timezone_interface.SetTimezoneWithPriority(
            "Language/Spoke",
            TIMEZONE_PRIORITY_LANGUAGE
        )
        assert self.timezone_interface.Timezone == "Language/Spoke"
        # check same priority overwrites
        self.timezone_interface.SetTimezoneWithPriority(
            "More/Lang",
            TIMEZONE_PRIORITY_LANGUAGE
        )
        assert self.timezone_interface.Timezone == "More/Lang"
        # check lower priority does not overwrite
        self.timezone_interface.SetTimezoneWithPriority(
            "Back/To/Defaults",
            TIMEZONE_PRIORITY_DEFAULT
        )
        assert self.timezone_interface.Timezone == "More/Lang"
        # check that the unprioritized property uses the highest priority
        # order of constants is guaranteed by testing elsewhere
        self.timezone_interface.Timezone = "Highest"
        assert self.timezone_interface.Timezone == "Highest"
        self.timezone_interface.SetTimezoneWithPriority(
            "Kick/Start",
            TIMEZONE_PRIORITY_KICKSTART
        )
        assert self.timezone_interface.Timezone == "Highest"

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self.timezone_interface, ks_in, ks_out)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        # System timezone
        timezone America/New_York
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart(self):
        """Test the timezone command."""
        ks_in = """
        timezone Europe/Prague
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_utc(self):
        """Test the timezone command with the UTC flag."""
        ks_in = """
        timezone Europe/Prague --utc
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague --utc
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_disabled(self):
        """Test the timesource command with ntp disabled."""
        ks_in = """
        timesource --ntp-disable
        """
        ks_out = """
        timesource --ntp-disable
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_server(self):
        """Test the timesource command with ntp servers."""
        ks_in = """
        timesource --ntp-server ntp.cesnet.cz
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_pool(self):
        """Test the timesource command with ntp pools."""
        ks_in = """
        timesource --ntp-pool ntp.cesnet.cz
        """
        ks_out = """
        timesource --ntp-pool=ntp.cesnet.cz
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_nts(self):
        """Test the timesource command with the nts option."""
        ks_in = """
        timesource --ntp-pool ntp.cesnet.cz --nts
        """
        ks_out = """
        timesource --ntp-pool=ntp.cesnet.cz --nts
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_all(self):
        """Test the timesource commands."""
        ks_in = """
        timesource --ntp-server ntp.cesnet.cz
        timesource --ntp-pool 0.fedora.pool.ntp.org
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        timesource --ntp-pool=0.fedora.pool.ntp.org
        """
        self._test_kickstart(ks_in, ks_out)

    def test_collect_requirements(self):
        """Test the requirements of the Timezone module."""
        # Check the default requirements.
        requirements = Requirement.from_structure_list(
            self.timezone_interface.CollectRequirements()
        )
        assert len(requirements) == 1
        assert requirements[0].type == "package"
        assert requirements[0].name == "chrony"

        # Check requirements with disabled NTP service.
        self.timezone_interface.NTPEnabled = False
        requirements = Requirement.from_structure_list(
            self.timezone_interface.CollectRequirements()
        )
        assert len(requirements) == 0

    @patch_dbus_publish_object
    def test_install_with_tasks_default(self, publisher):
        """Test install tasks - module in default state."""
        task_classes = [
            ConfigureHardwareClockTask,
            ConfigureTimezoneTask,
            ConfigureNTPTask,
        ]
        task_paths = self.timezone_interface.InstallWithTasks()
        task_objs = check_task_creation_list(task_paths, publisher, task_classes)

        # ConfigureHardwareClockTask
        obj = task_objs[0]
        assert obj.implementation._is_utc is False
        # ConfigureTimezoneTask
        obj = task_objs[1]
        assert obj.implementation._timezone == "America/New_York"
        assert obj.implementation._is_utc is False
        # ConfigureNTPTask
        obj = task_objs[2]
        assert obj.implementation._ntp_enabled is True
        assert obj.implementation._ntp_servers == []

    @patch_dbus_publish_object
    def test_install_with_tasks_configured(self, publisher):
        """Test install tasks - module in configured state."""
        self.timezone_interface.IsUTC = True
        self.timezone_interface.Timezone = "Asia/Tokyo"
        self.timezone_interface.NTPEnabled = False
        # --nontp and --ntpservers are mutually exclusive in kicstart but
        # there is no such enforcement in the module so for testing this is ok

        server = TimeSourceData()
        server.type = TIME_SOURCE_SERVER
        server.hostname = "clock1.example.com"
        server.options = ["iburst"]

        pool = TimeSourceData()
        pool.type = TIME_SOURCE_POOL
        pool.hostname = "clock2.example.com"

        self.timezone_interface.TimeSources = \
            TimeSourceData.to_structure_list([server, pool])

        task_classes = [
            ConfigureHardwareClockTask,
            ConfigureTimezoneTask,
            ConfigureNTPTask,
        ]
        task_paths = self.timezone_interface.InstallWithTasks()
        task_objs = check_task_creation_list(task_paths, publisher, task_classes)

        # ConfigureHardwareClockTask
        obj = task_objs[0]
        assert obj.implementation._is_utc is True

        # ConfigureTimezoneTask
        obj = task_objs[1]
        assert obj.implementation._timezone == "Asia/Tokyo"
        assert obj.implementation._is_utc is True

        # ConfigureNTPTask
        obj = task_objs[2]
        assert obj.implementation._ntp_enabled is False
        assert len(obj.implementation._ntp_servers) == 2
        assert compare_data(obj.implementation._ntp_servers[0], server)
        assert compare_data(obj.implementation._ntp_servers[1], pool)

    @patch_dbus_publish_object
    def test_geoloc_interface(self, publisher):
        """Test geolocation-related interface and implementation of Timezone"""
        task_path = self.timezone_interface.StartGeolocationWithTask()
        check_task_creation_list([task_path], publisher, [GeolocationTask])

        # without any actions, we should get empty GeolocationData
        new = GeolocationData.from_structure(self.timezone_interface.GeolocationResult)
        assert new.is_empty()

    def test_geoloc_result_callback(self):
        """Test geolocation task result callback"""
        result = GeolocationData.from_values(territory="", timezone="")
        self.timezone_module._set_geolocation_result(result)
        assert self.timezone_module.geolocation_result == result

    @patch("pyanaconda.modules.timezone.timezone.get_all_regions_and_timezones")
    def test_get_timezones(self, get_all_tz):
        """Test getting a listing of all valid timezones."""
        get_all_tz.return_value = OrderedDict([("foo", {"bar", "baz"})])
        # as the timezones for a region are listed as a set, we need to be a bit careful
        # when comparing the results
        result = self.timezone_interface.GetAllValidTimezones()
        assert list(result.keys()) == ["foo"]
        assert sorted(result["foo"]) == ['bar', 'baz']
        get_all_tz.assert_called_once()

    @patch("pyanaconda.modules.timezone.timezone.datetime")
    def test_get_system_date_time(self, fake_datetime):
        """Test getting system date and time."""
        # use a non-default timezone
        self.timezone_module._timezone = "Antarctica/South_Pole"
        # fake date object returned by now() call
        fake_date = MagicMock()
        fake_date.isoformat.return_value = "2023-06-22T18:49:36.878200"

        def fake_now(value):
            assert value == get_timezone("Antarctica/South_Pole")
            return fake_date

        fake_datetime.datetime.now.side_effect = fake_now
        assert self.timezone_interface.GetSystemDateTime() == "2023-06-22T18:49:36.878200"
        fake_date.isoformat.assert_called_once()

    @patch("pyanaconda.modules.timezone.timezone.set_system_date_time")
    def test_set_system_date_time(self, fake_set_time):
        """Test setting system date and time."""
        self.timezone_interface.SetSystemDateTime("2023-06-22T18:49:36.878200")
        fake_set_time.assert_called_once_with(year=2023,
                                              month=6,
                                              day=22,
                                              hour=18,
                                              minute=49,
                                              tz="America/New_York")
