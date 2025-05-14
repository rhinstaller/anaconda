#
# Brian C. Lane <bcl@redhat.com>
#
# Copyright 2015 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#
import unittest
from textwrap import dedent
from unittest.mock import Mock, patch

from pykickstart.errors import KickstartDeprecationWarning

from pyanaconda import kickstart
from pyanaconda.core.configuration.anaconda import AnacondaConfiguration
from pyanaconda.core.constants import (
    PASSWORD_POLICY_LUKS,
    PASSWORD_POLICY_ROOT,
    PASSWORD_POLICY_USER,
)
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from pyanaconda.pwpolicy import apply_password_policy_from_kickstart
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy


class PwPolicyTestCase(unittest.TestCase):
    ks = """
%anaconda
pwpolicy root --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy user --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy luks --strict --minlen=8 --minquality=50 --nochanges --emptyok
%end
"""

    def setUp(self):
        self.handler = kickstart.AnacondaKSHandler()
        self.ksparser = kickstart.AnacondaKSParser(self.handler)

    def test_pwpolicy(self):
        with self.assertWarns(KickstartDeprecationWarning):
            self.ksparser.readKickstartFromString(self.ks)

        assert isinstance(self.handler, kickstart.AnacondaKSHandler)
        assert isinstance(self.handler.anaconda, kickstart.AnacondaSectionHandler)

        eq_template = "pwpolicy %s --minlen=8 --minquality=50 --strict --nochanges --emptyok\n"
        for name in ["root", "user", "luks"]:
            assert str(self.handler.anaconda.pwpolicy.get_policy(name)) == eq_template % name    # pylint: disable=no-member

    @patch_dbus_get_proxy
    def test_apply_none_to_module(self, proxy_getter):
        ui_module = Mock()
        proxy_getter.return_value = ui_module

        apply_password_policy_from_kickstart(self.handler)
        ui_module.SetPasswordPolicies.assert_not_called()

    @patch_dbus_get_proxy
    def test_apply_policies_to_module(self, proxy_getter):
        ui_module = Mock()
        proxy_getter.return_value = ui_module

        ks_in = """
        %anaconda
        pwpolicy root --minlen=1 --minquality=10 --notempty --strict
        pwpolicy user --minlen=2 --minquality=20 --emptyok --notstrict
        pwpolicy luks --minlen=3 --minquality=30 --emptyok --strict
        %end
        """

        self.ksparser.readKickstartFromString(dedent(ks_in))
        apply_password_policy_from_kickstart(self.handler)

        root_policy = PasswordPolicy()
        root_policy.min_length = 1
        root_policy.min_quality = 10
        root_policy.is_strict = True
        root_policy.allow_empty = False

        user_policy = PasswordPolicy()
        user_policy.min_length = 2
        user_policy.min_quality = 20
        user_policy.is_strict = False
        user_policy.allow_empty = True

        luks_policy = PasswordPolicy()
        luks_policy.min_length = 3
        luks_policy.min_quality = 30
        luks_policy.is_strict = True
        luks_policy.allow_empty = True

        policies = {
            PASSWORD_POLICY_ROOT: root_policy,
            PASSWORD_POLICY_USER: user_policy,
            PASSWORD_POLICY_LUKS: luks_policy
        }

        ui_module.SetPasswordPolicies.assert_called_once_with(
            PasswordPolicy.to_structure_dict(policies)
        )

    @patch_dbus_get_proxy
    def test_apply_none_to_configuration(self, proxy_getter):
        anaconda_conf = AnacondaConfiguration.from_defaults()

        with patch("pyanaconda.pwpolicy.conf", anaconda_conf):
            apply_password_policy_from_kickstart(self.handler)

        assert anaconda_conf.ui.can_change_root is False
        assert anaconda_conf.ui.can_change_users is False

    @patch_dbus_get_proxy
    def test_apply_changesok_to_configuration(self, proxy_getter):
        anaconda_conf = AnacondaConfiguration.from_defaults()

        ks_in = """
        %anaconda
        pwpolicy root --changesok
        pwpolicy user --changesok
        pwpolicy luks --changesok
        %end
        """

        self.ksparser.readKickstartFromString(dedent(ks_in))

        with patch("pyanaconda.pwpolicy.conf", anaconda_conf):
            apply_password_policy_from_kickstart(self.handler)

        assert anaconda_conf.ui.can_change_root is True
        assert anaconda_conf.ui.can_change_users is True

    @patch_dbus_get_proxy
    def test_apply_nochanges_to_configuration(self, proxy_getter):
        anaconda_conf = AnacondaConfiguration.from_defaults()

        ks_in = """
        %anaconda
        pwpolicy root --nochanges
        pwpolicy user --nochanges
        pwpolicy luks --nochanges
        %end
        """

        self.ksparser.readKickstartFromString(dedent(ks_in))

        with patch("pyanaconda.pwpolicy.conf", anaconda_conf):
            apply_password_policy_from_kickstart(self.handler)

        assert anaconda_conf.ui.can_change_root is False
        assert anaconda_conf.ui.can_change_users is False
