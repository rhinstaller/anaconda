#
# Copyright (C) 2022  Red Hat, Inc.
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
from unittest import TestCase
from unittest.mock import Mock, patch

from requests.exceptions import RequestException

from pyanaconda.core.constants import GEOLOC_URL_FEDORA_GEOIP, GEOLOC_URL_HOSTIP
from pyanaconda.modules.common.structures.timezone import GeolocationData
from pyanaconda.modules.timezone.initialization import GeolocationTask


class MockRequestsGetResult:
    """Create a mock result of requests.get call to a geolocation provider"""

    def __init__(self, status_code, country_code, time_zone):
        self.status_code = status_code
        self._country_code = country_code
        self._time_zone = time_zone

    def json(self):
        """Provide fake JSON from the mock values"""
        result = {}
        if self._country_code:
            result["country_code"] = self._country_code
        if self._time_zone:
            result["time_zone"] = self._time_zone
        return result


class GeolocationTaskLocateTest(TestCase):
    """Test GeolocationTask._locate()"""

    @patch("pyanaconda.modules.timezone.initialization.requests.get",
           return_value=MockRequestsGetResult(200, "GB", "Europe/London"))
    def test_fgip_success(self, mock_get):
        """Test FedoraGeoIPProvider success"""
        task = GeolocationTask()
        result = task._locate(GEOLOC_URL_FEDORA_GEOIP)

        assert isinstance(result, GeolocationData)
        assert result.territory == "GB"
        assert result.timezone == "Europe/London"
        assert not result.is_empty()
        mock_get.assert_called_once()

    @patch("pyanaconda.modules.timezone.initialization.requests.get",
           return_value=MockRequestsGetResult(200, "GB", "this is invalid"))
    def test_fgip_bad_timezone(self, mock_get):
        """Test FedoraGeoIPProvider with bad time zone data"""
        task = GeolocationTask()
        result = task._locate(GEOLOC_URL_FEDORA_GEOIP)

        assert isinstance(result, GeolocationData)
        assert result.territory == "GB"
        assert result.timezone == "Europe/London"
        assert not result.is_empty()
        mock_get.assert_called_once()

    @patch("pyanaconda.modules.timezone.initialization.requests.get",
           return_value=MockRequestsGetResult(200, "", ""))
    def test_fgip_emptydata(self, mock_get):
        """Test FedoraGeoIPProvider with empty data"""
        task = GeolocationTask()
        result = task._locate(GEOLOC_URL_FEDORA_GEOIP)

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        mock_get.assert_called_once()

    @patch("pyanaconda.modules.timezone.initialization.requests.get",
           return_value=MockRequestsGetResult(503, "", ""))
    def test_fgip_failure(self, mock_get):
        """Test FedoraGeoIPProvider with HTTP failure"""
        task = GeolocationTask()
        with self.assertLogs(level="DEBUG") as logs:
            result = task._locate(GEOLOC_URL_FEDORA_GEOIP)

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        mock_get.assert_called_once()
        assert "failed with status code: 503" in "\n".join(logs.output)

    @patch("pyanaconda.modules.timezone.initialization.requests.get")
    def test_fgip_raise(self, mock_get):
        """Test FedoraGeoIPProvider handling of exceptions"""
        task = GeolocationTask()

        mock_get.side_effect = RequestException
        with self.assertLogs(level="DEBUG") as logs:
            result = task._locate(GEOLOC_URL_FEDORA_GEOIP)
        assert isinstance(result, GeolocationData)

        assert result.is_empty()
        mock_get.assert_called_once()
        assert "RequestException" in "\n".join(logs.output)

        mock_get.reset_mock()

        # This is technically cheating, ValueError is expected to be raised elsewhere than the
        # request itself. But it's all wrapped in a single try....except block so it is a good
        # enough approximation.
        mock_get.side_effect = ValueError
        with self.assertLogs(level="DEBUG") as logs:
            result = task._locate(GEOLOC_URL_FEDORA_GEOIP)

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        mock_get.assert_called_once()
        assert "Unable to decode" in "\n".join(logs.output)

    @patch("pyanaconda.modules.timezone.initialization.requests.get",
           return_value=MockRequestsGetResult(200, "GB", ""))
    def test_hip_success(self, mock_get):
        """Test HostipGeoIPProvider success"""
        task = GeolocationTask()
        result = task._locate(GEOLOC_URL_HOSTIP)

        assert isinstance(result, GeolocationData)
        assert result.territory == "GB"
        assert result.timezone == "Europe/London"
        assert not result.is_empty()
        mock_get.assert_called_once()


class GeolocationTaskRunTest(TestCase):
    """Test GeolocationTask.run()"""

    @patch("pyanaconda.modules.timezone.initialization.conf")
    def test_success(self, conf_mock):
        """Test success case for GeolocationTask"""
        conf_mock.timezone.geolocation_provider = GEOLOC_URL_FEDORA_GEOIP
        retval = GeolocationData.from_values(territory="territory", timezone="timezone")

        with patch.object(GeolocationTask, "_wait_for_network", return_value=True) as wfn_mock:
            with patch.object(GeolocationTask, "_locate", return_value=retval) as loc_mock:
                task = GeolocationTask()
                result = task.run()

        assert isinstance(result, GeolocationData)
        assert result.timezone == retval.timezone
        assert result.territory == retval.territory
        wfn_mock.assert_called_once_with()
        loc_mock.assert_called_once()

    @patch("pyanaconda.modules.timezone.initialization.conf")
    def test_no_network(self, conf_mock):
        """Test GeolocationTask with no network access"""
        conf_mock.timezone.geolocation_provider = GEOLOC_URL_FEDORA_GEOIP
        retval = GeolocationData.from_values(territory="territory", timezone="timezone")

        with self.assertLogs(level="DEBUG") as logs:
            with patch.object(GeolocationTask, "_wait_for_network", return_value=False) as wfn_mock:
                with patch.object(GeolocationTask, "_locate", return_value=retval) as loc_mock:
                    task = GeolocationTask()
                    result = task.run()

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        wfn_mock.assert_called_once_with()
        loc_mock.assert_not_called()
        assert "no network connection" in "\n".join(logs.output)

    @patch("pyanaconda.modules.timezone.initialization.conf")
    def test_no_result(self, conf_mock):
        """Test GeolocationTask with no viable result"""
        conf_mock.timezone.geolocation_provider = GEOLOC_URL_FEDORA_GEOIP
        retval = GeolocationData()  # empty by default

        with patch.object(GeolocationTask, "_wait_for_network", return_value=True) as wfn_mock:
            with patch.object(GeolocationTask, "_locate", return_value=retval) as loc_mock:
                task = GeolocationTask()
                result = task.run()

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        wfn_mock.assert_called_once_with()
        loc_mock.assert_called_once()

    @patch("pyanaconda.modules.timezone.initialization.conf")
    def test_empty_url(self, conf_mock):
        """Test GeolocationTask with no viable result"""
        conf_mock.timezone.geolocation_provider = ""
        retval = GeolocationData()  # empty by default

        with patch.object(GeolocationTask, "_wait_for_network", return_value=True) as wfn_mock:
            with patch.object(GeolocationTask, "_locate", return_value=retval) as loc_mock:
                task = GeolocationTask()
                result = task.run()

        assert isinstance(result, GeolocationData)
        assert result.is_empty()
        wfn_mock.assert_not_called()
        loc_mock.assert_not_called()


class MockNetworkProxy:
    """A mock Network module proxy with the Connected property

    Return Connected values as specified on creation, count accesses.
    """
    def __init__(self, connect_results=False):
        """Create the class

        :param [bool] connect_results: results to return in Connected
        """
        self._call_count = 0
        self._results = [False]
        if isinstance(connect_results, list) and len(connect_results) > 0:
            self._results = connect_results

    @property
    def Connected(self):
        """Return Connected values as specified on creation, count accesses.

        If asked more times than specified, return last value.
        """
        index = min(self._call_count, len(self._results)-1)
        self._call_count += 1
        return self._results[index]

    @property
    def call_count(self):
        return self._call_count


class GeolocationTaskWaitForNetworkTest(TestCase):
    """Test GeolocationTask._wait_for_network()"""

    @patch("pyanaconda.modules.timezone.initialization.NETWORK")
    @patch("pyanaconda.modules.timezone.initialization.is_module_available", return_value=True)
    @patch("pyanaconda.modules.timezone.initialization.time")
    def test_immediate_success(self, time_mock, avail_mock, net_mock):
        """Test waiting for network when already connected"""
        time_mock.sleep = Mock()
        time_mock.perf_counter = Mock()
        net_mock.get_proxy = Mock(return_value=MockNetworkProxy(connect_results=[True]))

        task = GeolocationTask()
        result = task._wait_for_network()

        assert result is True
        time_mock.sleep.assert_not_called()
        time_mock.perf_counter.assert_not_called()
        avail_mock.assert_called_once_with(net_mock)
        assert net_mock.get_proxy.return_value.call_count == 1

    @patch("pyanaconda.modules.timezone.initialization.NETWORK")
    @patch("pyanaconda.modules.timezone.initialization.is_module_available", return_value=False)
    @patch("pyanaconda.modules.timezone.initialization.time")
    def test_no_network(self, time_mock, avail_mock, net_mock):
        """Test waiting for network when no network available"""
        time_mock.sleep = Mock()
        time_mock.perf_counter = Mock(side_effect=[0, 1, 2, 3, 4, 65536])  # fake time out
        net_mock.get_proxy = Mock(return_value=MockNetworkProxy(connect_results=[False]))

        task = GeolocationTask()
        result = task._wait_for_network()

        assert result is False
        time_mock.sleep.assert_not_called()
        avail_mock.assert_called_once_with(net_mock)
        assert net_mock.get_proxy.return_value.call_count == 0

    @patch("pyanaconda.modules.timezone.initialization.NETWORK")
    @patch("pyanaconda.modules.timezone.initialization.is_module_available", return_value=True)
    @patch("pyanaconda.modules.timezone.initialization.time")
    def test_success_while_waiting(self, time_mock, avail_mock, net_mock):
        """Test waiting for network when network becomes available"""
        time_mock.sleep = Mock()
        time_mock.perf_counter = Mock(side_effect=[0, 0, 1, 2])  # init + 3 iterations only
        net_mock.get_proxy = Mock(return_value=MockNetworkProxy(connect_results=[
            False, False, False, True  # 1 before, 2 iterations keep going, 3rd succeeds
        ]))

        task = GeolocationTask()
        result = task._wait_for_network()

        assert result is True
        assert time_mock.sleep.call_count == 3
        avail_mock.assert_called_once_with(net_mock)
        assert net_mock.get_proxy.return_value.call_count == 4  # same as number of results

    @patch("pyanaconda.modules.timezone.initialization.NETWORK")
    @patch("pyanaconda.modules.timezone.initialization.is_module_available", return_value=True)
    @patch("pyanaconda.modules.timezone.initialization.time")
    def test_success_after_waiting(self, time_mock, avail_mock, net_mock):
        """Test waiting for network when network becomes available at the very last moment"""
        time_mock.sleep = Mock()
        time_mock.perf_counter = Mock(side_effect=[0, 0, 1, 2, 3, 4, 65536])  # fake time out
        net_mock.get_proxy = Mock(return_value=MockNetworkProxy(
            connect_results=[False] + [False] * 5 + [True]
            # 1 before, 5 iterations, 1 timeout interation, last exit
        ))

        task = GeolocationTask()
        result = task._wait_for_network()

        assert result is True
        assert time_mock.sleep.call_count == 5
        avail_mock.assert_called_once_with(net_mock)
        assert net_mock.get_proxy.return_value.call_count == 7  # same as number of results
