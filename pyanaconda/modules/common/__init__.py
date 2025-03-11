#
# Copyright (C) 2018 Red Hat, Inc.
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
import sys

from pyanaconda.core.path import set_mode

__all__ = ["init"]


def init(log_filename=None, log_stream=sys.stderr):
    """Do initial configuration of an Anaconda DBus module.

    This method should be imported and called from __main__.py of every
    Anaconda DBus module before any other import.

    :param log_filename: a file for logging or None
    :param log_stream: a stream for logging or None
    """
    import faulthandler
    faulthandler.enable()

    import logging
    handlers = []

    if log_stream:
        handlers.append(
            logging.StreamHandler(log_stream)
        )

    if log_filename:
        # Set correct permissions on log files from security reasons
        set_mode(log_filename)

        handlers.append(
            logging.FileHandler(log_filename)
        )

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers
    )

    import locale

    from pyanaconda.core.constants import DEFAULT_LANG
    locale.setlocale(locale.LC_ALL, DEFAULT_LANG)

    from pyanaconda.anaconda_loggers import get_module_logger
    from pyanaconda.core.configuration.anaconda import conf
    log = get_module_logger(__name__)
    log.debug("The configuration is loaded from: %s", conf.get_sources())
