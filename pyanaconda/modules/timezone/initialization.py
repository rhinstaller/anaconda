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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import time

import requests

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import NETWORK_CONNECTION_TIMEOUT
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.structures.timezone import GeolocationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.timezone import get_preferred_timezone, is_valid_timezone

log = get_module_logger(__name__)


class GeolocationTask(Task):
    """Run geolocation"""
    @property
    def name(self):
        return "Geolocate the system"

    def run(self):
        url = conf.timezone.geolocation_provider

        if not url:
            log.info("Geoloc: skipping because no provider was set")
            return GeolocationData()

        log.info("Geoloc: starting lookup using provider: %s", url)
        start_time = time.time()

        if not self._wait_for_network():
            log.error("Geoloc: no network connection")
            return GeolocationData()

        result = self._locate(url)
        log.info(
            "Geoloc: lookup finished in %1.1f seconds, result is valid: %s",
            time.time() - start_time,
            not result.is_empty()
        )
        return result

    def _wait_for_network(self, timeout=NETWORK_CONNECTION_TIMEOUT):
        """Wait until network is available, or time runs out

        :param float timeout: how long shall we try waiting
        :return bool: is there network connectivity
        """
        if not is_module_available(NETWORK):
            return False

        network = NETWORK.get_proxy()
        if network.Connected:
            return True

        log.info("Geoloc: Waiting for network to become available")

        interval = 0.1
        start = time.perf_counter()
        end = start + timeout
        while time.perf_counter() < end:
            time.sleep(interval)
            if network.Connected:
                return True

        return network.Connected

    def _locate(self, url):
        """Geolocate the computer using the service at given URL

        :param str url: URL to query
        :return GeolocationData: data structure describing geolocation results
        """
        try:
            log.info("Geoloc: querying the API")
            reply = requests.get(
                url,
                timeout=NETWORK_CONNECTION_TIMEOUT,
                verify=True
            )
            if reply.status_code == requests.codes.ok:  # pylint: disable=no-member
                json_reply = reply.json()
                territory = json_reply.get("country_code", "")
                timezone = json_reply.get("time_zone", "")

                # check if the timezone returned by the API is valid
                if not is_valid_timezone(timezone):
                    # try to get a timezone from the territory code
                    timezone = get_preferred_timezone(territory)

                if territory or timezone:
                    return GeolocationData.from_values(
                        territory=territory,
                        timezone=timezone,
                    )
            else:
                log.error("Geoloc: API lookup failed with status code: %s", reply.status_code)

        except requests.exceptions.RequestException as exc:
            log.debug("Geoloc: RequestException for API lookup:\n%s", exc)
        except ValueError as exc:
            log.debug("Geoloc: Unable to decode JSON:\n%s", exc)

        return GeolocationData()
