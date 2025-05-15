#
# Copyright (C) 2020  Red Hat, Inc.
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
import logging

import dnf.logging
import libdnf

DNF_LIBREPO_LOG = "/tmp/dnf.librepo.log"
DNF_LOGGER = "dnf"


def configure_dnf_logging():
    """Configure the DNF logging."""
    # Set up librepo.
    # This is still required even when the librepo has a separate logger because
    # DNF needs to have callbacks that the librepo log is written to be able to
    # process that log.
    libdnf.repo.LibrepoLog.removeAllHandlers()
    libdnf.repo.LibrepoLog.addHandler(DNF_LIBREPO_LOG)

    # Set up DNF. Increase the log level to the custom DDEBUG level.
    dnf_logger = logging.getLogger(DNF_LOGGER)
    dnf_logger.setLevel(dnf.logging.DDEBUG)
