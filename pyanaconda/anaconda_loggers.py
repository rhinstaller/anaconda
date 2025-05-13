#
# anaconda_loggers.py : provides Anaconda specififc loggers
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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

# Q: Why do we have a separate module for this?
#
# A: To avoid import cycles. The anaconda_logging module would be a natural
#    place for this function, but it unfrotunatelly imports the flags module.
#    And the flags module would have to import anaconda_logging to obtain the
#    get_module_logger() function, resulting in an import cycle.
#    We should be able to avoid this be placing the get_logger() function
#    in its own module that does not import any Anaconda modules other
#    than the constants module.

import logging

from pyanaconda.core import constants


def get_module_logger(module_name):
    """Return anaconda sub-logger based on a module __name__ attribute.

    Currently we just strip the "pyanaconda." prefix (if any) and then
    put the string behind "anaconda.". After thet we use the result
    to get the correspondong sub-logger.
    """
    if module_name.startswith("pyanaconda."):
        module_name = module_name[11:]
    return logging.getLogger("anaconda.%s" % module_name)


def get_anaconda_root_logger():
    return logging.getLogger(constants.LOGGER_ANACONDA_ROOT)


def get_main_logger():
    return logging.getLogger(constants.LOGGER_MAIN)


def get_stdout_logger():
    return logging.getLogger(constants.LOGGER_STDOUT)


def get_program_logger():
    return logging.getLogger(constants.LOGGER_PROGRAM)
