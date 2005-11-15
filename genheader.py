#!/usr/bin/python

import os
from struct import *
import rpm
import copy

# Types
RPM_NULL = 0
RPM_CHAR = 1
RPM_INT8 = 2
RPM_INT16 = 3
RPM_INT32 = 4
RPM_INT64 = 5 # Unused currently
RPM_STRING = 6
RPM_BIN = 7
RPM_STRING_ARRAY = 8
RPM_I18NSTRING = 9

stringTypes = [ RPM_STRING, RPM_STRING_ARRAY, RPM_I18NSTRING ]

formatTable = {
    RPM_CHAR : "!c",
    RPM_INT8 : "!B",
    RPM_INT16 : "!H",
    RPM_INT32 : "!I",
    RPM_INT64 : "!Q",
    RPM_STRING : "s",
    RPM_BIN : "s",
    RPM_STRING_ARRAY : "s",
    RPM_I18NSTRING : "s"
}

senseTable = { 
    "EQ": rpm.RPMSENSE_EQUAL,
    "LT": rpm.RPMSENSE_LESS,
    "GT": rpm.RPMSENSE_GREATER,
    "LE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_LESS,
    "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER
}

class YumHeader:
    def __init__(self,po):
        """Partial and dumbed down header generation for cd installation
           @param po
           @type po: PackageObject"""
        self.po = po
        self.store = ""
        self.offset = 0
        self.indexes = []
        self.tagtbl = { 
            'os': (rpm.RPMTAG_OS, RPM_STRING),
            'name': (rpm.RPMTAG_NAME, RPM_STRING),
            'epoch': (rpm.RPMTAG_EPOCH, RPM_INT32),
            'version': (rpm.RPMTAG_VERSION, RPM_STRING),
            'release': (rpm.RPMTAG_RELEASE, RPM_STRING),
            'arch': (rpm.RPMTAG_ARCH, RPM_STRING),
            'summary': (1004, RPM_STRING),
            'description': (1005, RPM_STRING),
            'providename': (rpm.RPMTAG_PROVIDENAME, RPM_STRING_ARRAY),
            'provideversion': (rpm.RPMTAG_PROVIDEVERSION, RPM_STRING_ARRAY),
            'provideflags': (rpm.RPMTAG_PROVIDEFLAGS, RPM_STRING_ARRAY)
        }
        if 'epoch' in self.po.simpleItems():
            self.po.simple['epoch'] = int(self.po.simple['epoch'])

    def __format(self, tag, tagtype, value):
        if not isinstance(value, (tuple, list)):
            return self.__formatSingle(tag, tagtype, value)
        else:
            count = len(value)
            data = ""
            for entry in value:
                (entrycount, entrydata) = self.__formatSingle(tag, tagtype, value)
                data += entrydata
            return (count, data)

    def __formatSingle(self, tag, tagtype, value):
        format = formatTable[tagtype]
        count = 1
        if tagtype == RPM_BIN:
            format = "%%d%s" % format
            count = len(value)
            data = pack(format % (count, value))
        elif tagtype in stringTypes:
            # Null terminate
            data = pack("%ds" % (len(value) + 1), value)
        else:     
            data = pack(format, value)
        return (count, data)

    def __alignTag(self, tagtype):
        """Return alignment data for aligning for ttype from offset
        self.offset."""
        if tagtype == RPM_INT16:
            align = (2 - (self.offset % 2)) % 2
        elif tagtype == RPM_INT32:
            align = (4 - (self.offset % 4)) % 4
        elif tagtype == RPM_INT64:
            align = (8 - (self.offset % 8)) % 8
        else:
            align = 0
        return '\x00' * align

    def convertTag(self, tag):
        if self.tagtbl.has_key(tag):
            (rpmtag, tagtype) = self.tagtbl[tag]
            self.addTag(rpmtag, tagtype, self.po.returnSimple(tag))

    def addTag(self, rpmtag, tagtype, value):
            (count, data) = self.__format(rpmtag, tagtype, value)
            pad = self.__alignTag(tagtype)
            self.offset += len(pad)
            self.indexes.append((rpmtag, tagtype,self.offset, count))
            self.store += pad + data 
            self.offset += len(data)

    def mungEpoch(self):
        epoch = self.po.returnSimple('epoch')
        (rpmtag, tagtype) = self.tagtbl['epoch']
        if epoch is not None:
            self.addTag(rpmtag, tagtype, int(epoch))

    def generateProvides(self):
        self.po.simple['provideversion'] = [ "%s-%s" % (self.po.returnSimple('version'), self.po.returnSimple('release')) ]
        self.po.simple['providename'] = [self.po.returnSimple['name']]
        self.po.simple['provideversion'] = [ "%s-%s" % (self.po.returnSimple('version'), self.po.returnSimple('release')) ]
        self.po.returnSimple['provideflags'] = [senseTable["EQ"]]
        self.convertTag('providename')
        self.convertTag('provideversion')
        self.convertTag('provideflags')
        self.convertTag('provideflags')

    def str(self):
        self.po.simple['os'] = 'linux'
        self.convertTag('os')
        for tag in ['name','version', 'release', 'arch', 'summary', 'description']:
            if tag in self.po.simpleItems():
                self.convertTag(tag)
        self.mungEpoch()
        
        magic = '\x8e\xad\xe8'
        hdr_start_fmt= '!3sB4xii'
        index_fmt = '!4I'
        version = 1
        hdr = pack(hdr_start_fmt, magic, version, len(self.indexes),  len(self.store))
        for (tag, tagtype, offset, count) in self.indexes:
            hdr += pack(index_fmt, tag, tagtype, offset, count)
        hdr += self.store
        return hdr
