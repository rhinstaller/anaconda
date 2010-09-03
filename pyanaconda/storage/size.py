# size.py
# Python module to represent storage sizes
#
# Copyright (C) 2010  Red Hat, Inc.
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
# Red Hat Author(s): David Cantrell <dcantrell@redhat.com>

from decimal import Decimal
from decimal import InvalidOperation

from errors import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

# Decimal prefixes for different size increments, along with the name
# and accepted abbreviation for the prefix.  These prefixes are all
# for 'bytes'.
_decimalPrefix = [(1000, _("kilo"), _("k")),
                  (1000**2, _("mega"), _("M")),
                  (1000**3, _("giga"), _("G")),
                  (1000**4, _("tera"), _("T")),
                  (1000**5, _("peta"), _("P")),
                  (1000**6, _("exa"), _("E")),
                  (1000**7, _("zetta"), _("Z")),
                  (1000**8, _("yotta"), _("Y"))]

# Binary prefixes for the different size increments.  Same structure
# as the above list.
_binaryPrefix = [(1024, _("kibi"), _("Ki")),
                 (1024**2, _("mebi"), _("Mi")),
                 (1024**3, _("gibi"), _("Gi")),
                 (1024**4, _("tebi"), None),
                 (1024**5, _("pebi"), None),
                 (1024**6, _("ebi"), None),
                 (1024**7, _("zebi"), None),
                 (1024**8, _("yobi"), None)]

_bytes = [_('b'), _('byte'), _('bytes')]
_prefixes = _decimalPrefix + _binaryPrefix

def _makeSpecs(prefix, abbr):
    """ Internal method used to generate a list of specifiers. """
    specs = []

    if prefix:
        specs.append(prefix.lower() + _("byte"))
        specs.append(prefix.lower() + _("bytes"))

    if abbr:
        specs.append(abbr.lower() + _("b"))

    return specs

def _parseSpec(spec):
    """ Parse string representation of size. """
    if not spec:
        return None

    # first check for strings like "47 MB" or "1.21 GB"
    fields = spec.split()
    if len(fields) == 2:
        # assume value for the first field and specifier for the second
        size = Decimal(fields[0])
        specifier = fields[1].lower()

        if size < 1:
            raise SizeNotPositiveError("spec= param must be >0")

        if specifier in _bytes:
            return size

        for factor, prefix, abbr in _prefixes:
            check = _makeSpecs(prefix, abbr)

            if specifier in check:
                return size * factor
    elif len(fields) > 2 or len(fields) < 1:
        # too much data in the string
        return None
    else:
        # no space between value and specifier
        try:
            size = Decimal(spec)

            if size < 1:
                raise SizeNotPositiveError("spec= param must be >0")

            if str(size) == spec:
                return size
        except InvalidOperation:
            pass

        for factor, prefix, abbr in _prefixes:
            check = _makeSpecs(prefix, abbr)
            match = filter(lambda x: spec.lower().endswith(x), check)

            if match != [] and len(match) == 1:
                size = Decimal(spec[:len(match[0])].strip())

                if size < 1:
                    raise SizeNotPositiveError("spec= param must be >0")

                return size * factor

    return None

class Size(Decimal):
    """ Common class to represent storage device and filesystem sizes.
        Can handle parsing strings such as 45MB or 6.7GB to initialize
        itself, or can be initialized with a numerical size in bytes.
        Also generates human readable strings to a specified number of
        decimal places.
    """

    def __new__(cls, bytes=None, spec=None):
        """ Initialize a new Size object.  Must pass either bytes or spec,
            but not both.  The bytes parameter is a numerical value for
            the size this object represents, in bytes.  The spec parameter
            is a string specification of the size using any of the size
            specifiers in the _decimalPrefix or _binaryPrefix lists combined
            with a 'b' or 'B'.  For example, to specify 640 kilobytes, you
            could pass any of these parameter:

                spec="640kb"
                spec="640 kb"
                spec="640KB"
                spec="640 KB"
                spec="640 kilobytes"

            If you want to use spec to pass a bytes value, you can use the
            letter 'b' or 'B' or simply leave the specifier off and bytes
            will be assumed.
        """
        if bytes and spec:
            raise SizeParamsError("only specify one parameter")

        if bytes:
            if type(bytes).__name__ in ["int", "long"] and bytes > 0:
                self = Decimal.__new__(cls, value=bytes)
            else:
                raise SizeNotPositiveError("bytes= param must be >0")
        elif spec:
            self = Decimal.__new__(cls, value=_parseSpec(spec))
        else:
            raise SizeParamsError("missing bytes= or spec=")

        return self

    def _trimEnd(self, val):
        """ Internal method to trim trailing zeros. """
        while val != '' and val.endswith('0'):
            val = val[:-1]

        if val.endswith('.'):
            val = val[:-1]

        return val

    def convertTo(self, spec="b"):
        """ Return the size in the units indicated by the specifier.  The
            specifier can be prefixes from the _decimalPrefix and
            _binaryPrefix lists combined with 'b' or 'B' for abbreviations)
            or 'bytes' (for prefixes like kilo or mega).  The size is
            returned as a Decimal.
        """
        spec = spec.lower()

        if spec in _bytes:
            return self

        for factor, prefix, abbr in _prefixes:
            check = _makeSpecs(prefix, abbr)

            if spec in check:
                return self / Decimal(factor)

        return None

    def humanReadable(self, places=2):
        """ Return a string representation of this size with appropriate
            size specifier and in the specified number of decimal places
            (default: 2).
        """
        if places < 1:
            raise SizePlacesError("places= must be >1")

        totalLen = places + 2
        check = self._trimEnd("%d" % self)

        if len(check) == totalLen:
            return "%s b" % check

        for factor, prefix, abbr in _prefixes:
            check = self / Decimal(factor)

            i = places
            while i > 0:
                rounder = Decimal("." + "1".zfill(i))
                newcheck = check.quantize(rounder)
                retval = str(newcheck)

                if len(retval) == totalLen:
                    if abbr:
                        return retval + " " + abbr + _("b")
                    elif newcheck == 1:
                        return retval + " " + prefix + _("byte")
                    else:
                        return retval + " " + prefix + _("bytes")

                i -= 1

        return None
