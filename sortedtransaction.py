#!/usr/bin/python

from yum.transactioninfo import TransactionData, TransactionMember
from yum.Errors import YumBaseError

import urlparse
urlparse.uses_fragment.append('media')

WHITE = 0
GREY = 1
BLACK = 2

class SortableTransactionData(TransactionData):
    def __init__(self):
        self._sorted = []
        self.path = []
        self.loops = []
        self.changed = True
        TransactionData.__init__(self)

    def _visit(self, txmbr):
        self.path.append(txmbr.name)
        txmbr.sortColour = GREY
        for (relation, reltype) in txmbr.relatedto:
            if reltype != 'dependson':
                continue 
            vertex = self.getMembers(pkgtup=relation)[0]
            if vertex.sortColour == GREY:
                self._doLoop(vertex.name)
            if vertex.sortColour == WHITE:
                self._visit(vertex)
        txmbr.sortColour = BLACK
        self._sorted.insert(0, txmbr.pkgtup)

    def _doLoop(self, name):
        self.path.append(name)
        loop = self.path[self.path.index(self.path[-1]):]
        if len(loop) > 2:
            self.loops.append(loop)

    def add(self, txmember):
        txmember.sortColour = WHITE
        TransactionData.add(self, txmember)
        self.changed = True

    def remove(self, pkgtup):
        TransactionData.remove(self, pkgtup)
        self.changed = True

    def sort(self):
        if self._sorted and not self.changed:
            return self._sorted
        self._sorted = []
        self.changed = False
        # loop over all members
        for txmbr in self.getMembers():
            if txmbr.sortColour == WHITE:
                self.path = [ ]
                self._visit(txmbr)
        self._sorted.reverse()
        return self._sorted

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
                return 0
            else:
                return int(fragid)
        except (KeyError, AttributeError):
            return 0

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
                id = self.__getMedia(txmbr.po)
                if id:
                    self.reqmedia[id].remove(pktup)
                del txmbr
                SortableTransactionData.remove(self, pkgtup)

class TransactionConstraintMetError(YumBaseError):
    def __init__(self, args=None):
        YumBaseError.__init__(self)
        self.args = args
        
class ConstrainedTransactionData(SortableTransactionData):
    def __init__(self, constraint=lambda txmbr: False):
        """Arbitrary constraint on transaction member
           @param constraint form:
              function(self, TransactionMember)
              constraint function returns True/False.
           @type constraint function"""
        self.constraint = constraint
        SortableTransactionData.__init__(self)

    def add(self, txmbr):
        """@param txmbr: TransactionMember
           @raise TransactionConstraintMetError: if 
               constraint returns True when adding"""
        if self.constraint and not self.constraint(txmbr):
            SortableTransactionData.add(self, txmbr)
        else:
            raise TransactionConstraintMetError("Constraint met")



