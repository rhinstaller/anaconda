#!/usr/bin/python

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
            for key in self.reqmedia[self.curmedia]:
                returnlist.extend(self.pkgdict[key])

            return returnlist

        if self.reqmedia[self.curmedia].has_key(pkgtup):
            return self.pkgdict[pkgtup]
        else:
            return []

    def add(self, txmember):
        if txmember.output_state in TS_INSTALL_STATES:
            id = self.__getMedia(txmember.po)
            if id:
                if id not in self.reqmedia.keys():
                    self.reqmedia[id] = [ txmember.pkgtup ]
                else:
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
