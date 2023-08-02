#
# product.py: product identification string
#
# Copyright (C) 2003  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.core.product import get_product_is_final_release, get_product_name, \
    get_product_version, get_product_short_name
from pyanaconda.core.i18n import _

__all__ = ["isFinal", "productName", "productVersion", "shortProductName", "distributionText"]


# TODO: Remove all usages of these variables by replacing them with the actual getters from
#  pyanaconda.core.product, then resolve the helper below, finally remove this file.
isFinal = get_product_is_final_release()
productName = get_product_name()
productVersion = get_product_version()
shortProductName = get_product_short_name()


def distributionText():
    return _("%(productName)s %(productVersion)s INSTALLATION") % {
        "productName": get_product_name().upper(),
        "productVersion": get_product_version().upper()
    }
