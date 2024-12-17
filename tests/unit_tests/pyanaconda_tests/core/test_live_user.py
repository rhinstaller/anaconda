# -*- coding: utf-8 -*-
#
# Copyright (C) 2023  Red Hat, Inc.
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

from unittest import TestCase
from unittest.mock import patch, Mock
from pyanaconda.core.live_user import get_live_user, User


class GetLiveUserTests(TestCase):

    @patch("pyanaconda.core.live_user.conf")
    @patch("pyanaconda.core.live_user.getpwuid")
    def test_get_live_user_not_on_live(self, getpwuid_mock, conf_mock):
        # not live = early exit
        conf_mock.system.provides_liveuser = False
        assert get_live_user() is None
        getpwuid_mock.assert_not_called()

    @patch("pyanaconda.core.live_user.conf")
    @patch("pyanaconda.core.live_user.getpwuid")
    @patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "1024"})
    def test_get_live_user(self, getpwuid_mock, conf_mock):
        # live and has user
        conf_mock.system.provides_liveuser = True
        getpwuid_mock.return_value = Mock(pw_uid=1024, pw_dir='/home/liveuser', pw_name='liveuser')
        assert get_live_user() == User(name="liveuser",
                                       uid=1024,
                                       env_prune=("GDK_BACKEND",),
                                       env_add={
                                           "XDG_RUNTIME_DIR": "/run/user/1024",
                                           "USER": "liveuser",
                                           "HOME": "/home/liveuser",
                                       })
        getpwuid_mock.assert_called_once_with(1024)
        getpwuid_mock.reset_mock()

    @patch("pyanaconda.core.live_user.conf")
    @patch("pyanaconda.core.live_user.getpwuid")
    @patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "1024"})
    def test_get_live_user_with_failed_getpwuid(self, getpwuid_mock, conf_mock):
        # supposedly live but missing user
        conf_mock.system.provides_liveuser = True
        getpwuid_mock.side_effect = KeyError
        assert get_live_user() is None
        getpwuid_mock.assert_called_once_with(1024)

    @patch("pyanaconda.core.live_user.conf")
    @patch("pyanaconda.core.live_user.getpwuid")
    @patch.dict("pyanaconda.core.live_user.os.environ", {})
    def test_get_live_user_with_missing_pkexec_env(self, getpwuid_mock, conf_mock):

        conf_mock.system.provides_liveuser = True

        assert get_live_user() is None
        getpwuid_mock.assert_not_called()

    @patch("pyanaconda.core.live_user.conf")
    def test_get_live_user_failed_on_pkexec_env(self, conf_mock):
        conf_mock.system.provides_liveuser = True

        with patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": ""}):
            assert get_live_user() is None

        with patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "hello world"}):
            assert get_live_user() is None

        with patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "-1"}):
            assert get_live_user() is None

        with patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "999999999999999999999999"}):
            assert get_live_user() is None

        with patch.dict("pyanaconda.core.live_user.os.environ", {"PKEXEC_UID": "0"}):
            assert get_live_user() is None
