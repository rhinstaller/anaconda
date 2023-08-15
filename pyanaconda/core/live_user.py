#
# live_user.py:  Provide information about liveuser user from the
# currently running system
#
# Copyright (C) 2023
# Red Hat, Inc.  All rights reserved.
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

from collections import namedtuple
from pwd import getpwnam

from pyanaconda.core.configuration.anaconda import conf


User = namedtuple("User", ["name", "uid", "env_add", "env_prune"])


def get_live_user():
    """Get the user name and uid of the liveuser user.

    :return: user name and uid as namedtuple or None
    :rtype: namedtuple User["name", "uid"]  | None
    """
    if not conf.system.provides_liveuser:
        return None

    try:
        username = "liveuser"
        uid = getpwnam(username).pw_uid
        env_prune = ("GDK_BACKEND",)
        env_add = {
            "XDG_RUNTIME_DIR": "/run/user/{}".format(uid),
            "USER": username,
            "HOME": "/home/{}".format(username),
        }
        return User(name=username,
                    uid=uid,
                    env_add=env_add,
                    env_prune=env_prune)
    except KeyError:
        return None
