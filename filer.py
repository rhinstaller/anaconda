#!/usr/bin/python
#
# Copyright (C) 2008  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Chris Lumens <clumens@redhat.com>
#
import xmlrpclib
import socket

# An abstraction to make various bug reporting systems all act the same.  This
# library requires the use of other system-specific python modules to interact
# with the bug systems themselves.  A disadvantage here is that we expect all
# systems to have a bugzilla-like interface for now.  That could change as I
# see how more systems behave.

class LoginError(Exception):
    """An error occurred while logging into the bug reporting system."""
    def __init__(self, bugUrl, username):
        self.bugUrl = bugUrl
        self.username = username

    def __str__(self):
        return "Could not login to %s with username %s" % (self.bugUrl, self.username)

class CommunicationError(Exception):
    """Some miscellaneous error occurred while communicating with the
       bug reporting system.  This could include XML-RPC errors, passing
       bad data, or network problems."""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return "Error communicating with bug system: %s" % self.msg


# These classes don't do anything except say that automated bug filing are not
# supported.  They also define the interface that concrete classes should use,
# as this is what will be expected by exception.py.
class AbstractFiler(object):
    def __init__(self, bugUrl=None, develVersion=None):
        self.bugUrl = bugUrl
        self.develVersion = develVersion

    def login(self, username, password):
        raise NotImplementedError

    def createbug(self, check_args=False, *args, **kwargs):
        raise NotImplementedError

    def getbug(self, id):
        raise NotImplementedError

    def getbugs(self, idlist):
        raise NotImplementedError

    def getversion(self, ver, prod):
        raise NotImplementedError

    def query(self, query):
        raise NotImplementedError

    def supportsFiling(self):
        return False

class AbstractBug(object):
    def __init__(self, filer, bug=None, *args, **kwargs):
        self.filer = filer

    def __str__(self):
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError

    def addCC(self, address):
        raise NotImplementedError

    def addcomment(self, comment):
        raise NotImplementedError

    def attachfile(self, file, description, **kwargs):
        raise NotImplementedError

    def close(self, resolution, dupeid=0, comment=''):
        raise NotImplementedError

    def id(self):
        raise NotImplementedError

    def setstatus(self, status, comment=''):
        raise NotImplementedError

    def setassignee(self, assigned_to='', reporter='', comment=''):
        raise NotImplementedError

    # Do all bug reporting systems have some sort of whiteboard?
    def getwhiteboard(self, which=''):
        raise NotImplementedError

    def appendwhiteboard(self, text, which=''):
        raise NotImplementedError

    def prependwhitebaord(self, text, which=''):
        raise NotImplementedError

    def setwhiteboard(self, text, which=''):
        raise NotImplementedError


# Concrete classes for automatically filing bugs against Bugzilla instances.
# This requires the python-bugzilla module to do almost all of the real work.
# We basically just make some really thin wrappers around it here since we
# expect all bug filing systems to act similar to bugzilla.
class BugzillaFiler(AbstractFiler):
    def __withBugzillaDo(self, fn):
        try:
            retval = fn(self._bz)
            return retval
        except xmlrpclib.ProtocolError, e:
            raise CommunicationError(str(e))
        except xmlrpclib.Fault, e:
            raise ValueError(str(e))
        except socket.error, e:
            raise CommunicationError(str(e))

    def __init__(self, bugUrl=None, develVersion=None):
        AbstractFiler.__init__(self, bugUrl=bugUrl, develVersion=develVersion)
        self._bz = None

    def login(self, username, password):
        import bugzilla

        self._bz = bugzilla.Bugzilla(url=self.bugUrl)

        retval = self._bz.login(username, password)
        if not retval:
            raise LoginError(self.bugUrl, username)

        return retval

    def createbug(self, check_args=False, *args, **kwargs):
        whiteboards = []

        for (key, val) in kwargs.items():
            if key.endswith("_whiteboard"):
                wb = key.split("_")[0]
                whiteboards.append((wb, val))
                kwargs.pop(key)

        bug = self.__withBugzillaDo(lambda b: b.createbug(**kwargs))
        for (wb, val) in whiteboards:
            bug.setwhiteboard(val, which=wb)

        return BugzillaBug(self, bug=bug)

    def getbug(self, id):
        return BugzillaBug(self, bug=self.__withBugzillaDo(lambda b: b.getbug(id)))

    def getbugs(self, idlist):
        lst = self.__withBugzillaDo(lambda b: b.getbugs(idlist))
        return map(lambda b: BugzillaBug(self, bug=b), lst)

    def getversion(self, ver, prod):
        details = self.__withBugzillaDo(lambda b: b._proxy.bugzilla.getProductDetails(prod))
        bugzillaVers = details[1]
        bugzillaVers.sort()

        if ver not in bugzillaVers:
            if self.develVersion:
                return self.develVersion
            else:
                return bugzillaVers[-1]
        else:
            return ver

    def query(self, query):
        lst = self.__withBugzillaDo(lambda b: b.query(query))
        return map(lambda b: BugzillaBug(self, bug=b), lst)

    def supportsFiling(self):
        return True

class BugzillaBug(AbstractBug):
    def __withBugDo(self, fn):
        try:
            retval = fn(self._bug)
            return retval
        except xmlrpclib.ProtocolError, e:
            raise CommunicationError(str(e))
        except xmlrpclib.Fault, e:
            raise ValueError(str(e))
        except socket.error, e:
            raise CommunicationError(str(e))

    def __init__(self, filer, bug=None, *args, **kwargs):
        import bugzilla

        self.filer = filer

        if not bug:
            self._bug = bugzilla.Bug(self.filer, *args, **kwargs)
        else:
            self._bug = bug

    def __str__(self):
        return self._bug.__str__()

    def __repr__(self):
        return self._bug.__repr__()

    def addCC(self, address):
        try:
            return self.filer._bz._updatecc(self._bug.bug_id, [address], 'add')
        except xmlrpclib.ProtocolError, e:
            raise CommunicationError(str(e))
        except xmlrpclib.Fault, e:
            raise ValueError(str(e))
        except socket.error, e:
            raise CommunicationError(str(e))

    def addcomment(self, comment):
        return self.__withBugDo(lambda b: b.addcomment(comment))

    def attachfile(self, file, description, **kwargs):
        try:
            return self.filer._bz.attachfile(self._bug.bug_id, file, description, **kwargs)
        except xmlrpclib.ProtocolError, e:
            raise CommunicationError(str(e))
        except xmlrpclib.Fault, e:
            raise ValueError(str(e))
        except socket.error, e:
            raise CommunicationError(str(e))

    def id(self):
        return self._bug.bug_id

    def close(self, resolution, dupeid=0, comment=''):
        return self.__withBugDo(lambda b: b.close(resolution, dupeid=dupeid,
                                                  comment=comment))

    def setstatus(self, status, comment=''):
        return self.__withBugDo(lambda b: b.setstatus(status, comment=comment))

    def setassignee(self, assigned_to='', reporter='', comment=''):
        return self.__withBugDo(lambda b: b.setassignee(assigned_to=assigned_to,
                                                        reporter=reporter,
                                                        comment=comment))

    def getwhiteboard(self, which='status'):
        return self.__withBugDo(lambda b: b.getwhiteboard(which=which))

    def appendwhiteboard(self, text, which='status'):
        return self.__withBugDo(lambda b: b.appendwhiteboard(text, which=which))

    def prependwhitebaord(self, text, which='status'):
        return self.__withBugDo(lambda b: b.prependwhiteboard(text, which=which))

    def setwhiteboard(self, text, which='status'):
        return self.__withBugDo(lambda b: b.setwhiteboard(text, which=which))
