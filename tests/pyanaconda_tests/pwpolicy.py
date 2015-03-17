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
from mock import Mock
import unittest

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        import sys

        sys.modules["anaconda_log"] = Mock()
        sys.modules["block"] = Mock()

        from pyanaconda import kickstart
        self.kickstart = kickstart
        self.handler = kickstart.AnacondaKSHandler()
        self.ksparser = kickstart.AnacondaKSParser(self.handler)

class PwPolicyTestCase(BaseTestCase):
    ks = """
%anaconda
pwpolicy root --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy user --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy luks --strict --minlen=8 --minquality=50 --nochanges --emptyok
%end
"""
    def pwpolicy_test(self):
        self.ksparser.readKickstartFromString(self.ks)

        self.assertIsInstance(self.handler, self.kickstart.AnacondaKSHandler)
        self.assertIsInstance(self.handler.anaconda, self.kickstart.AnacondaSectionHandler)

        eq_template = "pwpolicy %s --minlen=8 --minquality=50 --strict --nochanges --emptyok\n"
        for name in ["root", "user", "luks"]:
            self.assertEqual(str(self.handler.anaconda.pwpolicy.get_policy(name)), eq_template % name)    # pylint: disable=no-member
