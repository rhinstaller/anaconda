#
# Copyright (C) 2012-2013  Red Hat, Inc.
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

"""
Module facilitating the work with NTP servers and NTP daemon's configuration

"""

import os
import re
import shutil
import tempfile

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.async_utils import async_action_nowait
from pyanaconda.core.constants import (
    NTP_SERVER_NOK,
    NTP_SERVER_OK,
    NTP_SERVER_QUERY,
    NTP_SERVER_TIMEOUT,
    THREAD_NTP_SERVER_CHECK,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.signal import Signal
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.structures.timezone import TimeSourceData

NTP_CONFIG_FILE = "/etc/chrony.conf"

#example line:
#server 0.fedora.pool.ntp.org iburst
SRV_LINE_REGEXP = re.compile(r"^\s*(server|pool)\s*([-a-zA-Z.0-9]+)\s?([a-zA-Z0-9\s]*)$")
SRV_NOARG_OPTIONS = ["burst", "iburst", "nts", "prefer", "require", "trust", "noselect", "xleave"]
SRV_ARG_OPTIONS = ["key", "minpoll", "maxpoll"]

# Description of an NTP server status.
NTP_SERVER_STATUS_DESCRIPTIONS = {
    NTP_SERVER_OK: N_("status: working"),
    NTP_SERVER_NOK: N_("status: not working"),
    NTP_SERVER_QUERY: N_("checking status")
}

log = get_module_logger(__name__)


class NTPconfigError(Exception):
    """Exception class for NTP related problems"""
    pass


def get_ntp_server_summary(server, states):
    """Generate a summary of an NTP server and its status.

    :param server: an NTP server
    :type server: an instance of TimeSourceData
    :param states: a cache of NTP server states
    :type states: an instance of NTPServerStatusCache
    :return: a string with a summary
    """
    return "{} ({})".format(
        server.hostname,
        states.get_status_description(server)
    )


def get_ntp_servers_summary(servers, states):
    """Generate a summary of NTP servers and their states.

    :param servers: a list of NTP servers
    :type servers: a list of TimeSourceData
    :param states: a cache of NTP server states
    :type states: an instance of NTPServerStatusCache
    :return: a string with a summary
    """
    summary = _("NTP servers:")

    for server in servers:
        summary += "\n" + get_ntp_server_summary(server, states)

    if not servers:
        summary += " " + _("not configured")

    return summary


def ntp_server_working(server_hostname, nts_enabled):
    """Tries to do an NTP request to the server (timeout may take some time).

    If NTS is enabled, try making a TCP connection to the NTS-KE port instead.

    :param server_hostname: a host name or an IP address of an NTP server
    :type server_hostname: string
    :return: True if the given server is reachable and working, False otherwise
    :rtype: bool
    """
    directive = ["server", server_hostname, "iburst", "maxsamples", "1"]

    if nts_enabled:
        directive.append("nts")

    arguments = ["-Q", " ".join(directive), "-t", str(NTP_SERVER_TIMEOUT)]
    return execWithRedirect("chronyd", arguments) == 0


def get_servers_from_config(conf_file_path=NTP_CONFIG_FILE):
    """Get NTP servers from a configuration file.

    Goes through the chronyd's configuration file looking for lines starting
    with 'server'.

    :param conf_file_path: a path to the chronyd's configuration file
    :return: servers found in the chronyd's configuration
    :rtype: a list of TimeSourceData instances
    """
    servers = []

    try:
        with open(conf_file_path, "r") as conf_file:
            for line in conf_file:
                match = SRV_LINE_REGEXP.match(line)

                if not match:
                    continue

                server = TimeSourceData()
                server.type = match.group(1).upper()
                server.hostname = match.group(2)
                server.options = []

                words = match.group(3).lower().split()
                skip_argument = False

                for i, word in enumerate(words):
                    if skip_argument:
                        skip_argument = False
                        continue
                    if word in SRV_NOARG_OPTIONS:
                        server.options.append(word)
                    elif word in SRV_ARG_OPTIONS and i + 1 < len(words):
                        server.options.append(' '.join(words[i:i+2]))
                        skip_argument = True
                    else:
                        log.debug("Unknown NTP server option %s", word)

                servers.append(server)

    except OSError as e:
        msg = "Cannot open config file {} for reading ({})."
        raise NTPconfigError(msg.format(conf_file_path, e.strerror)) from e

    return servers


def save_servers_to_config(servers, conf_file_path=NTP_CONFIG_FILE, out_file_path=None):
    """Save NTP servers to a configuration file.

    Replaces the pools and servers defined in the chronyd's configuration file
    with the given ones. If the out_file is not None, then it is used for the
    resulting config.

    :param servers: a list of NTP servers and pools
    :type servers: a list of TimeSourceData instances
    :param conf_file_path: a path to the chronyd's configuration file
    :param out_file_path: a path to the file used for the resulting config
    """
    temp_path = None

    try:
        old_conf_file = open(conf_file_path, "r")
    except OSError as e:
        msg = "Cannot open config file {} for reading ({})."
        raise NTPconfigError(msg.format(conf_file_path, e.strerror)) from e

    if out_file_path:
        try:
            new_conf_file = open(out_file_path, "w")
        except OSError as e:
            msg = "Cannot open new config file {} for writing ({})."
            raise NTPconfigError(msg.format(out_file_path, e.strerror)) from e
    else:
        try:
            (fields, temp_path) = tempfile.mkstemp()
            new_conf_file = os.fdopen(fields, "w")
        except OSError as e:
            msg = "Cannot open temporary file {} for writing ({})."
            raise NTPconfigError(msg.format(temp_path, e.strerror)) from e

    heading = "# These servers were defined in the installation:\n"

    # write info about the origin of the following lines
    new_conf_file.write(heading)

    # write new servers and pools
    for server in servers:
        args = [server.type.lower(), server.hostname] + server.options
        line = " ".join(args) + "\n"
        new_conf_file.write(line)

    new_conf_file.write("\n")

    # copy non-server lines from the old config and skip our heading
    for line in old_conf_file:
        if not SRV_LINE_REGEXP.match(line) and line != heading:
            new_conf_file.write(line)

    old_conf_file.close()
    new_conf_file.close()

    if not out_file_path:
        try:
            # Use copy rather then move to get the correct selinux context
            shutil.copyfile(temp_path, conf_file_path)
            os.unlink(temp_path)

        except OSError as oserr:
            msg = "Cannot replace the old config with the new one ({})."
            raise NTPconfigError(msg.format(oserr.strerror)) from oserr


class NTPServerStatusCache:
    """The cache of NTP server states."""

    def __init__(self):
        self._cache = {}
        self._changed = Signal()

    @property
    def changed(self):
        """The status changed signal."""
        return self._changed

    def get_status(self, server):
        """Get the status of the given NTP server.

        :param TimeSourceData server: an NTP server
        :return int: a status of the NTP server
        """
        return self._cache.get(
            server.hostname,
            NTP_SERVER_QUERY
        )

    def get_status_description(self, server):
        """Get the status description of the given NTP server.

        :param TimeSourceData server: an NTP server
        :return str: a status description of the NTP server
        """
        status = self.get_status(server)
        return _(NTP_SERVER_STATUS_DESCRIPTIONS[status])

    def check_status(self, server):
        """Asynchronously check if given NTP servers appear to be working.

        :param TimeSourceData server: an NTP server
        """
        # Get a hostname and NTS option.
        hostname = server.hostname
        nts_enabled = "nts" in server.options

        # Reset the current status.
        self._set_status(hostname, NTP_SERVER_QUERY)

        # Start the check.
        thread_manager.add_thread(
            prefix=THREAD_NTP_SERVER_CHECK,
            target=self._check_status,
            args=(hostname, nts_enabled)
        )

    def _set_status(self, hostname, status):
        """Set the status of the given NTP server.

        :param str hostname: a hostname of an NTP server
        :return int: a status of the NTP server
        """
        self._cache[hostname] = status

    @async_action_nowait
    def _report_status_changed(self):
        """Emit the status changed signal.

        Run callbacks in the context of the main loop,
        so they will not affect the running thread.
        """
        self._changed.emit()

    def _check_status(self, hostname, nts_enabled):
        """Check if an NTP server appears to be working.

        :param str hostname: a hostname of an NTP server
        """
        log.debug("Checking NTP server %s", hostname)
        result = ntp_server_working(hostname, nts_enabled)

        if result:
            log.debug("NTP server %s appears to be working.", hostname)
            self._set_status(hostname, NTP_SERVER_OK)
        else:
            log.debug("NTP server %s appears not to be working.", hostname)
            self._set_status(hostname, NTP_SERVER_NOK)

        self._report_status_changed()
