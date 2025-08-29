#
# flags.py: global anaconda flags
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
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
from dataclasses import dataclass, field

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import ANACONDA_ENVIRON

log = get_module_logger(__name__)


@dataclass(slots=True)
class Flags:
    """
    Limit the Anaconda Flags to just the ones listed here.
    """
    use_rd: bool = False
    rd_question: bool = True
    preexisting_wayland: bool = False
    preexisting_x11: bool = False
    automatedInstall: bool = False
    eject: bool = True

    # ksprompt is whether or not to prompt for missing ksdata
    ksprompt: bool = True
    rescue_mode: bool = False
    kexec: bool = False

    # current runtime environments
    environs: list[str] = field(default_factory=lambda: [ANACONDA_ENVIRON])


flags = Flags()
