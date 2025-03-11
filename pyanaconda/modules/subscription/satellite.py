#
# Satellite support purpose library.
#
# Copyright (C) 2024 Red Hat, Inc.
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

import os
import tempfile

from requests import RequestException

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants, util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.path import make_directories
from pyanaconda.core.payload import ProxyString, ProxyStringError

log = get_module_logger(__name__)

# the well-known path of the Satellite instance URL where
# the provisioning script should be located
PROVISIONING_SCRIPT_SUB_PATH = "/pub/katello-rhsm-consumer"


def download_satellite_provisioning_script(satellite_url, proxy_url=None):
    """Download provisioning script from a Red Hat Satellite instance.

    Download the provisioning script from a Satellite instance and return
    it as a string.

    Satellite instances usually have self signed certificates and also some tweaks
    are usually required in rhsm.conf to connect to a customer run Satellite instance
    instead of to Hosted Candlepin for subscription purposes.

    Each Satellite instance thus hosts a provisioning script available over plain
    HTTP that client machines can download and execute. This script has minimal dependencies
    and provisions the machine to be able to talk to the one given Satellite instance
    by installing it's self signed certificates and adjusting rhsm.conf.

    NOTE: As the script is downloaded over plain HTTP it is advised to ever only
          provision machines from a Satellite instance on a trusted network, to
          avoid the possibility of the provisioning script being tempered with
          during transit.

    :param str satellite_url: Satellite instance URL
    :param proxy_url: proxy URL to use when fetching the script
    :type proxy_url: str or None if not set
    :returns: True on success, False otherwise
    """
    # make sure the URL starts with protocol
    if not satellite_url.startswith("http"):
        satellite_url = "http://" + satellite_url

    # construct the URL pointing to the provisioning script
    script_url = satellite_url + PROVISIONING_SCRIPT_SUB_PATH

    log.debug("subscription: fetching Satellite provisioning script from: %s", script_url)

    headers = {"user-agent": constants.USER_AGENT}
    proxies = {}
    provisioning_script = ""

    # process proxy URL (if any)
    if proxy_url is not None:
        try:
            proxy = ProxyString(proxy_url)
            proxies = {"http": proxy.url,
                       "https": proxy.url}
        except ProxyStringError as e:
            log.info("subscription: failed to parse proxy when fetching Satellite"
                     " provisioning script %s: %s",
                     proxy_url, e)

    with util.requests_session() as session:
        try:
            # NOTE: we explicitly don't verify SSL certificates while
            #       downloading the provisioning script as the Satellite
            #       instance will most likely have it's own self signed certs that
            #       will only be trusted once the provisioning script runs
            result = session.get(script_url, headers=headers,
                                 proxies=proxies, verify=False,
                                 timeout=constants.NETWORK_CONNECTION_TIMEOUT)
            if result.ok:
                provisioning_script = result.text
                result.close()
                log.debug("subscription: Satellite provisioning script downloaded (%d characters)",
                          len(provisioning_script))
                return provisioning_script
            else:
                log.debug("subscription: server returned %i code when downloading"
                          " Satellite provisioning script", result.status_code)
                result.close()
                return None
        except RequestException as e:
            log.debug("subscription: can't download Satellite provisioning script"
                      " from %s with proxy: %s. Error: %s", script_url, proxies, e)
            return None


def run_satellite_provisioning_script(provisioning_script=None, run_on_target_system=False):
    """Run the Satellite provisioning script.

    Each Satellite instance provides a provisioning script that will
    enable the currently running environment to talk to the given
    Satellite instance.

    This means that the self-signed certificates of the given
    Satellite instance will be installed to the system but also some
    necessary changes will be done to rhsm.conf.

    As we need to provision both the installation environment *and* the target system
    to talk to Satellite we need to run the provisioning script twice.
    - once in the installation environment
    - and once on the target system.

    This is achieved by running this function first in the installation environment
    with run_on_target_system == False before a registration attempt.
    And then in the installation phase with run_on_target_system == True.

    Implementation wise we just always run the script from a tempfile.

    That way we can easily run it in the installation environment as well
    as in the target system chroot with minimum code needed to make sure
    it exists where we need it

    :param str provisioning_script: content of the Satellite provisioning script
                                    or None if no script is available
    :param str run_on_target_system: run in the target system chroot instead,
                                     otherwise run in the installation environment
    :return: True on success, False otherwise
    :rtype: bool
    """
    # first check we actually have the script
    if provisioning_script is None:
        log.warning("subscription: satellite provisioning script not available")
        return False

    # now that we have something to run, check where to run it
    if run_on_target_system:
        # run in the target system chroot
        sysroot = conf.target.system_root
    else:
        # run in installation environment
        sysroot = "/"

    # create the tempfile containing the script in the sysroot in /tmp, just in case
    sysroot_tmp = util.join_paths(sysroot, "/tmp")
    # make sure the path exists
    make_directories(sysroot_tmp)
    with tempfile.NamedTemporaryFile(mode="w+t", dir=sysroot_tmp, prefix="satellite-") as tf:
        # write the provisioning script to the tempfile & flush any caches, just in case
        tf.write(provisioning_script)
        tf.flush()
        # We always set root to the correct sysroot, so the script will always
        # look like it is in /tmp. So just split the randomly generated file name
        # and combine it with /tmp to get sysroot specific script path.
        filename = os.path.basename(tf.name)
        chroot_script_path = os.path.join("/tmp", filename)
        # and execute it in the sysroot
        rc = util.execWithRedirect("bash", argv=[chroot_script_path], root=sysroot)
        if rc == 0:
            log.debug("subscription: satellite provisioning script executed successfully")
            return True
        else:
            log.debug("subscription: satellite provisioning script executed with error")
            return False
