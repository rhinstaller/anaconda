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
from pykickstart.base import BaseData, KickstartCommand
from pykickstart.errors import KickstartValueError, formatErrorMsg
from pykickstart.options import KSOptionParser

import warnings
from pyanaconda.i18n import _

class F22_PwPolicyData(BaseData):
    """ Kickstart Data object to hold information about pwpolicy. """
    removedKeywords = BaseData.removedKeywords
    removedAttrs = BaseData.removedAttrs

    def __init__(self, *args, **kwargs):
        BaseData.__init__(self, *args, **kwargs)
        self.name = kwargs.get("name", "")
        self.minlen = kwargs.get("minlen", 8)
        self.minquality = kwargs.get("minquality", 50)
        self.strict = kwargs.get("strict", True)
        self.changesok = kwargs.get("changesok", False)
        self.emptyok = kwargs.get("emptyok", True)

    def __eq__(self, y):
        if not y:
            return False

        return self.name == y.name

    def __ne__(self, y):
        return not self == y

    def __str__(self):
        retval = BaseData.__str__(self)

        if self.name != "":
            retval += "pwpolicy"
            retval += self._getArgsAsStr() + "\n"

        return retval

    def _getArgsAsStr(self):
        retval = ""

        retval += " %s" % self.name
        retval += " --minlen=%d" % self.minlen
        retval += " --minquality=%d" % self.minquality

        if self.strict:
            retval += " --strict"
        else:
            retval += " --notstrict"
        if self.changesok:
            retval += " --changesok"
        else:
            retval += " --nochanges"
        if self.emptyok:
            retval += " --emptyok"
        else:
            retval += " --notempty"

        return retval

class F22_PwPolicy(KickstartCommand):
    """ Kickstart command implementing password policy. """
    removedKeywords = KickstartCommand.removedKeywords
    removedAttrs = KickstartCommand.removedAttrs

    def __init__(self, writePriority=0, *args, **kwargs):
        KickstartCommand.__init__(self, writePriority, *args, **kwargs)
        self.op = self._getParser()

        self.policyList = kwargs.get("policyList", [])

    def __str__(self):
        retval = ""
        for policy in self.policyList:
            retval += policy.__str__()

        return retval

    def _getParser(self):
        op = KSOptionParser()
        op.add_option("--minlen", type="int")
        op.add_option("--minquality", type="int")
        op.add_option("--strict", action="store_true")
        op.add_option("--notstrict", dest="strict", action="store_false")
        op.add_option("--changesok", action="store_true")
        op.add_option("--nochanges", dest="changesok", action="store_false")
        op.add_option("--emptyok", action="store_true")
        op.add_option("--notempty", dest="emptyok", action="store_false")
        return op

    def parse(self, args):
        (opts, extra) = self.op.parse_args(args=args, lineno=self.lineno)
        if len(extra) != 1:
            raise KickstartValueError(formatErrorMsg(self.lineno, msg=_("policy name required for %s") % "pwpolicy"))

        pd = self.handler.PwPolicyData()
        self._setToObj(self.op, opts, pd)
        pd.lineno = self.lineno
        pd.name = extra[0]

        # Check for duplicates in the data list.
        if pd in self.dataList():
            warnings.warn(_("A %s with the name %s has already been defined.") % ("pwpolicy", pd.name))

        return pd

    def dataList(self):
        return self.policyList

    def get_policy(self, name):
        """ Get the policy by name

        :param str name: Name of the policy to return.

        """
        policy = [p for p in self.policyList if p.name == name]
        if policy:
            return policy[0]
        else:
            return None
