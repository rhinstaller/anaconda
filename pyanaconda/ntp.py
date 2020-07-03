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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

"""
Module facilitating the work with NTP servers and NTP daemon's configuration

"""

import re
import os
import tempfile
import shutil
import ntplib
import socket

from pyanaconda import isys
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.constants import THREAD_SYNC_TIME_BASENAME
from pyanaconda.modules.common.structures.timezone import TimeSourceData

NTP_CONFIG_FILE = "/etc/chrony.conf"

#example line:
#server 0.fedora.pool.ntp.org iburst
SRV_LINE_REGEXP = re.compile(r"^\s*(server|pool)\s*([-a-zA-Z.0-9]+)\s*[a-zA-Z]+\s*$")

#treat pools as four servers with the same name
SERVERS_PER_POOL = 4


class NTPconfigError(Exception):
    """Exception class for NTP related problems"""
    pass


def ntp_server_working(server_hostname):
    """Tries to do an NTP request to the server (timeout may take some time).

    :param server_hostname: a host name or an IP address of an NTP server
    :type server_hostname: string
    :return: True if the given server is reachable and working, False otherwise
    :rtype: bool
    """
    client = ntplib.NTPClient()

    try:
        client.request(server_hostname)
    except ntplib.NTPException:
        return False
    # address related error
    except socket.gaierror:
        return False
    # socket related error
    # (including "Network is unreachable")
    except socket.error:
        return False

    return True


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
                server.options = ["iburst"]
                servers.append(server)

    except IOError as ioerr:
        msg = "Cannot open config file {} for reading ({})."
        raise NTPconfigError(msg.format(conf_file_path, ioerr.strerror))

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
    except IOError as ioerr:
        msg = "Cannot open config file {} for reading ({})."
        raise NTPconfigError(msg.format(conf_file_path, ioerr.strerror))

    if out_file_path:
        try:
            new_conf_file = open(out_file_path, "w")
        except IOError as ioerr:
            msg = "Cannot open new config file {} for writing ({})."
            raise NTPconfigError(msg.format(out_file_path, ioerr.strerror))
    else:
        try:
            (fields, temp_path) = tempfile.mkstemp()
            new_conf_file = os.fdopen(fields, "w")
        except IOError as ioerr:
            msg = "Cannot open temporary file {} for writing ({})."
            raise NTPconfigError(msg.format(temp_path, ioerr.strerror))

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
            raise NTPconfigError(msg.format(oserr.strerror))


def _one_time_sync(server, callback=None):
    """Synchronize the system time with a given NTP server.

    Synchronize the system time with a given NTP server. Note that this
    function is blocking and will not return until the time gets synced or
    querying server fails (may take some time before timeouting).

    :param server: an NTP server
    :type server: an instance of TimeSourceData
    :param callback: callback function to run after sync or failure
    :type callback: a function taking one boolean argument (success)
    :return: True if the sync was successful, False otherwise
    """

    client = ntplib.NTPClient()
    try:
        results = client.request(server.hostname)
        isys.set_system_time(int(results.tx_time))
        success = True
    except ntplib.NTPException:
        success = False
    except socket.gaierror:
        success = False

    if callback is not None:
        callback(success)

    return success


def one_time_sync_async(server, callback=None):
    """Asynchronously synchronize the system time with a given NTP server.

    Asynchronously synchronize the system time with a given NTP server. This
    function is non-blocking it starts a new thread for synchronization and
    returns. Use callback argument to specify the function called when the
    new thread finishes if needed.

    :param server: an NTP server
    :type server: an instance of TimeSourceData
    :param callback: callback function to run after sync or failure
    :type callback: a function taking one boolean argument (success)
    """
    thread_name = "%s_%s" % (THREAD_SYNC_TIME_BASENAME, server.hostname)

    # syncing with the same server running
    if threadMgr.get(thread_name):
        return

    threadMgr.add(AnacondaThread(
        name=thread_name,
        target=_one_time_sync,
        args=(server, callback)
    ))
