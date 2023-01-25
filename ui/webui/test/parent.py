#!/usr/bin/python3
#
# Copyright (C) 2023 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import os
import sys

def setup_paths():
    BASE_DIR = os.path.normpath(os.path.dirname(__file__)+'/..')
    TEST_DIR = f'{BASE_DIR}/test'
    BOTS_DIR = f'{BASE_DIR}/bots'

    sys.path.append(BOTS_DIR)
    sys.path.append(f'{TEST_DIR}/common')
    sys.path.append(f'{BOTS_DIR}/machine')
