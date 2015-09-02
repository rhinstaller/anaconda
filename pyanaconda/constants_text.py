#
# constants_text.py: text mode constants
#
# Copyright (C) 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
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

# pylint: disable=wildcard-import
from pyanaconda.constants import *

# Make the return calls from the UIScreen input() function more clear
INPUT_PROCESSED = None
INPUT_DISCARDED = False

# default screen height in number of lines (24 lines is the default for serial
# consoles + 1 line for the tmux bar)
DEFAULT_SCREEN_HEIGHT = 23
