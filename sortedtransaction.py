#
# sortedtransaction.py
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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

from yum.transactioninfo import TransactionData, TransactionMember, SortableTransactionData
from yum.constants import *
from yum.Errors import YumBaseError

import urlparse
urlparse.uses_fragment.append('media')

import logging
log = logging.getLogger("anaconda")


class SplitMediaTransactionData(SortableTransactionData):
    def __init__(self):
        SortableTransactionData.__init__(self)
        self.reqmedia = {}
        self.curmedia = 0 

    def __getMedia(self, po):
        try:
            uri = po.returnSimple('basepath')
            (scheme, netloc, path, query, fragid) = urlparse.urlsplit(uri)
            if scheme != "media" or not fragid:
                return -99
            else:
                return int(fragid)
        except (KeyError, AttributeError):
            return -99

    def getMembers(self, pkgtup=None):
        if not self.curmedia:
            return TransactionData.getMembers(self, pkgtup)
        if pkgtup is None:
            returnlist = []
            for ele in self.reqmedia[self.curmedia]:
                returnlist.extend(self.pkgdict[ele])

            return returnlist

        if pkgtup in self.reqmedia[self.curmedia]:
            return self.pkgdict[pkgtup]
        else:
            return []

    def add(self, txmember):
        if txmember.output_state in TS_INSTALL_STATES:
            id = self.__getMedia(txmember.po)
            if id:
                if id not in self.reqmedia.keys():
                    self.reqmedia[id] = [ txmember.pkgtup ]
                elif txmember.pkgtup not in self.reqmedia[id]:
                    self.reqmedia[id].append(txmember.pkgtup)
        SortableTransactionData.add(self, txmember)

    def remove(self, pkgtup):
        if not self.pkgdict.has_key(pkgtup):
            return
        txmembers = self.pkgdict[pkgtup]
        if len(txmembers) > 0:
            for txmbr in txmembers:
                if txmbr.output_state not in TS_INSTALL_STATES:
                    continue
                id = self.__getMedia(txmbr.po)
                if id:
                    self.reqmedia[id].remove(pkgtup)
                    if len(self.reqmedia[id]) == 0:
                        self.reqmedia.pop(id)
                del txmbr
                SortableTransactionData.remove(self, pkgtup)
