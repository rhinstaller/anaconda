#
# Copyright (C) 2021  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.util import execWithRedirect, execWithCapture
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["start_service", "stop_service", "restart_service", "is_service_running",
           "is_service_installed", "enable_service", "disable_service"]


def _run_systemctl(command, service, root="/"):
    """Runs 'systemctl command service'

    :param str command: command to run on the service
    :param str service: name of the service to work on
    :return: exit status of the systemctl run
    """

    args = [command, service]
    if root != "/":
        args += ["--root", root]

    ret = execWithRedirect("systemctl", args)

    return ret


def start_service(service):
    """Start a systemd service in the installation environment

    Runs 'systemctl start service'.

    :param str service: name of the service to start
    :return: exit status of the systemctl run
    """
    return _run_systemctl("start", service)


def stop_service(service):
    """Stop a systemd service in the installation environment

    Runs 'systemctl stop service'.

    :param str service: name of the service to stop
    :return: exit status of the systemctl run
    """
    return _run_systemctl("stop", service)


def restart_service(service):
    """Restart a systemd service in the installation environment

    Runs 'systemctl restart service'.

    :param str service: name of the service to restart
    :return: exit status of the systemctl run
    """
    return _run_systemctl("restart", service)


def is_service_running(service):
    """Is a systemd service running in the installation environment?

    Runs 'systemctl status service'.

    :param str service: name of the service to check
    :return: was the service found
    """
    ret = _run_systemctl("status", service)

    return ret == 0


def is_service_installed(service, root=None):
    """Is a systemd service installed?

    Runs 'systemctl list-unit-files' to determine if the service exists.

    Root defaults to sysroot, but can be set. Use "/" for checking installation environment.

    :param str service: name of the service to check
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    if not service.endswith(".service"):
        service += ".service"

    args = ["list-unit-files", service, "--no-legend"]

    if root != "/":
        args += ["--root", root]

    unit_file = execWithCapture("systemctl", args)

    return bool(unit_file)


def enable_service(service, root=None):
    """ Enable a systemd service in the sysroot.

    Runs 'systemctl enable service'.

    :param str service: name of the service to enable
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    ret = _run_systemctl("enable", service, root=root)

    if ret != 0:
        raise ValueError("Error enabling service %s: %s" % (service, ret))


def disable_service(service, root=None):
    """ Disable a systemd service in the sysroot.

    Runs 'systemctl disable service'.

    :param str service: name of the service to disable
    :param str root: path to the sysroot or None to use default sysroot path
    """
    if root is None:
        root = conf.target.system_root

    # we ignore the error so we can disable services even if they don't
    # exist, because that's effectively disabled
    ret = _run_systemctl("disable", service, root=root)

    if ret != 0:
        log.warning("Disabling %s failed. It probably doesn't exist", service)
