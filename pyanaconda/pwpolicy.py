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
from pykickstart.errors import KickstartParseError
from pykickstart.options import KSOptionParser
from pykickstart.version import F22

import warnings
from pyanaconda.core.i18n import _


class F22_PwPolicyData(BaseData):
    """ Kickstart Data object to hold information about pwpolicy. """
    removedKeywords = BaseData.removedKeywords
    removedAttrs = BaseData.removedAttrs

    def __init__(self, *args, **kwargs):
        BaseData.__init__(self, *args, **kwargs)
        self.name = kwargs.get("name", "")
        self.minlen = kwargs.get("minlen", 6)
        self.minquality = kwargs.get("minquality", 1)
        self.strict = kwargs.get("strict", False)
        self.changesok = kwargs.get("changesok", False)
        self.emptyok = kwargs.get("emptyok", True)

        # The defaults specified above are used only for password input via the UI
        # during a partial kickstart installations.
        # Fully interactive installs (no kickstart is specified by the user)
        # use the default set by the interactive defaults built-in kickstart file
        # (data/interactive-defaults.ks).
        # Automated kickstart installs simply ignore the password policy as the policy
        # only applies to the UI, not for passwords specified in kickstart.

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

    # pylint: disable=keyword-arg-before-vararg
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
        op = KSOptionParser(prog="pwpolicy", version=F22, description="""
                            Set the policy to use for the named password
                            entry.""")

        op.add_argument("--minlen", type=int, version=F22, help="""
                        Name of the password entry, currently supported
                        values are: root, user and luks""")
        op.add_argument("--minquality", type=int, version=F22, help="""
                        Minimum libpwquality to consider good. When using
                        ``--strict`` it will not allow passwords with a
                        quality lower than this.""")
        op.add_argument("--strict", action="store_true", version=F22, help="""
                        Strict password enforcement. Passwords not meeting
                        the ``--minquality`` level will not be allowed.""")
        op.add_argument("--notstrict", dest="strict", action="store_false",
                        version=F22, help="""
                        Passwords not meeting the ``--minquality`` level
                        will be allowed after Done is clicked twice.""")
        op.add_argument("--changesok", action="store_true", version=F22,
                        help="""Allow empty password.""")
        op.add_argument("--nochanges", dest="changesok", action="store_false",
                        version=F22, help="""
                        Do not allow UI to be used to change the password/user
                        if it has been set in the kickstart.""")
        op.add_argument("--emptyok", action="store_true", version=F22, default=True,
                        help="""Allow empty password.""")
        op.add_argument("--notempty", dest="emptyok", action="store_false",
                        version=F22, help="""
                        Don't allow an empty password.""")
        return op

    def parse(self, args):
        (ns, extra) = self.op.parse_known_args(args=args, lineno=self.lineno)
        if len(extra) != 1:
            raise KickstartParseError(lineno=self.lineno, msg=_("policy name required for %s") % "pwpolicy")

        pd = self.handler.PwPolicyData()
        self.set_to_obj(ns, pd)
        pd.lineno = self.lineno
        pd.name = extra[0]

        # Check for duplicates in the data list.
        if pd in self.dataList():
            warnings.warn(_("A %(command)s with the name %(policyName)s has already been defined.") % {"command": "pwpolicy", "policyName": pd.name})

        return pd

    def dataList(self):
        return self.policyList

    def get_policy(self, name, fallback_to_default=False):
        """ Get the policy by name

        :param str name: Name of the policy to return.
        :param bool fallback_to_default: If true return default policy if policy with the given `name` doesn't exists.
        """
        policy = [p for p in self.policyList if p.name == name]
        if policy:
            return policy[0]
        elif fallback_to_default:
            return self.handler.PwPolicyData()
        else:
            return None
