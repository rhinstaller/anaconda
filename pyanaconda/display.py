#
# display.py:  graphical display setup for the Anaconda GUI
#
# Copyright (C) 2024 Neal Gompa. All rights reserved.
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
# Author(s):  Neal Gompa <neal@gompa.dev>
#


from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
log = get_module_logger(__name__)
stdout_log = get_stdout_logger()


# general display startup
def setup_display(anaconda, options):
    """Setup the display for the installation environment.

    :param anaconda: instance of the Anaconda class
    :param options: command line/boot options
    """

    if "x11" in kernel_arguments:
        from pyanaconda import display_x11
        display_x11.setup_display(anaconda, options)
    else:
        from pyanaconda import display_wayland
        display_wayland.setup_display(anaconda, options)
