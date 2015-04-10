# Translation functions we use all over the place
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

__all__ = ["_", "N_", "P_", "C_", "CN_", "CP_"]

import gettext

_ = lambda x: gettext.translation("anaconda", fallback=True).ugettext(x) if x != "" else u""
N_ = lambda x: x
P_ = lambda x, y, z: gettext.translation("anaconda", fallback=True).ungettext(x, y, z)

# This is equivalent to "pgettext" in GNU gettext. The pgettext functions
# are not exported by Python, but all they really do is a stick a EOT
# character between msgctxt and msgid and check that msgctxt isn't part
# of the return value.
def C_(msgctxt, msgid):
    ctxid = "%s\x04%s" % (msgctxt, msgid)
    translation = _(ctxid)

    # If there is no translation for msgctxt<EOT>msgid, return only msgid
    if translation == ctxid:
        return msgid
    else:
        return translation

# Mark as translatable with context
CN_ = lambda c, x: x

# npgettext; i.e., gettext with plural form and context
def CP_(msgctxt, msgid, msgid_plural, n):
    ctxid = "%s\x04%s" % (msgctxt, msgid)
    translation = P_(ctxid, msgid_plural, n)

    # If the returned value is msgctxt<EOT>msgid, ngettext was trying to
    # fallback to msgid. We don't add msgctxt to msgid_plural, so any other
    # return value is correct.
    if translation == ctxid:
        return msgid
    else:
        return translation
