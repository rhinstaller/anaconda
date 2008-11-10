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
    """The base class for Filer objects.  This is an abstract class.

       Within this class's help, Bug refers to a concrete AbstractBug subclass
       and Filer refers to a concrete AbstractFiler subclass.

       A Filer object communicates with a bug filing system - like bugzilla -
       that a distribution uses to track defects.  Install classes specify
       what bug filing system they use by instantiating a subclass of
       AbstractFiler.  The intention is that each subclass of AbstractFiler
       will make use of some system library to handle the actual communication
       with the bug filing system.  For now, all systems will be assumed to act
       like bugzilla.

       Methods in this class should raise the following exceptions:

       CommunicationError -- For all problems communicating with the remote
                             bug filing system.
       LoginError         -- For invalid login information.
       ValueError         -- For all other operations where the client
                             supplied values are not correct.
    """
    def __init__(self, bugUrl=None, develVersion=None, defaultProduct=None):
        """Create a new AbstractFiler instance.  This method need not be
           overridden by subclasses.

           bugUrl       -- The URL of the bug filing system.
           develVersion -- What version of the product should be treated as
                           the development version.  This is used in case
                           anaconda attempts to file bugs against invalid
                           versions.  It need not be set.
           defaultProduct -- The product bugs should be filed against, should
                             anaconda get an invalid product name from the
                             boot media.  This must be set.
        """
        self.bugUrl = bugUrl
        self.develVersion = develVersion
        self.defaultProduct = defaultProduct

    def login(self, username, password):
        """Using the given username and password, attempt to login to the
           bug filing system.  This method must be provided by all subclasses,
           and should raise LoginError if login is unsuccessful.
        """
        raise NotImplementedError

    def createbug(self, *args, **kwargs):
        """Create a new bug.  The kwargs dictionary is all the arguments that
           should be used when creating the new bug and is entirely up to the
           subclass to handle.  This method must be provided by all subclasses.
           On success, it should return a Bug instance.
        """
        raise NotImplementedError

    def getbug(self, id):
        """Search for a bug given by id and return it.  This method must be
           provided by all subclasses.  On success, it should return a Bug
           instance.  On error, it should return an instance that is empty.
        """
        raise NotImplementedError

    def getbugs(self, idlist):
        """Search for all the bugs given by the IDs in idlist and return.
           This method must be provided by all subclasses.  On success, it
           should return a list of Bug instances, or an empty instance for
           invalid IDs.
        """
        raise NotImplementedError

    def getproduct(self, prod):
        """Verify that prod is a valid product name.  If it is, return that
           same product name.  If not, return self.defaultProduct.  This method
           queries the bug filing system for a list of valid products.  It must
           be provided by all subclasses.
        """
        raise NotImplementedError

    def getversion(self, ver, prod):
        """Verify that ver is a valid version number for the product name prod.
           If it is, return that same version number.  If not, return
           self.develVersion if it exists or the latest version number
           otherwise.  This method queries the bug filing system for a list of
           valid versions numbers.  It must be provided by all subclasses.
        """
        raise NotImplementedError

    def query(self, query):
        """Perform the provided query and return a list of Bug instances that
           meet the query.  What the query is depends on the exact bug filing
           system, though anaconda will treat it as a dictionary of bug
           attibutes since this is what bugzilla expects.  Other filing systems
           will need to take extra work to munge this data into the expected
           format.  This method must be provided by all subclasses.
        """
        raise NotImplementedError

    def supportsFiling(self):
        """Does this class support filing bugs?  All subclasses should override
           this method and return True, or automatic filing will not work.  The
           base install class will use this method, so automatic filing will
           not be attempted by anaconda on unknown products.
        """
        return False

class AbstractBug(object):
    """The base class for Bug objects.  This is an abstract class.

       Within this class's help, Bug refers to a concrete AbstractBug subclass
       and Filer refers to a concrete AbstractFiler subclass.

       A Bug object represents one single bug within a Filer.  This is where
       most of the interesting stuff happens - attaching files, adding comments
       and email addresses, and modifying whiteboards.  Subclasses of this
       class are returned by most operations within a Filer subclass.  For now,
       all bugs will be assumed to act like bugzilla's bugs.

       Bug objects wrap objects in the underlying module that communicates with
       the bug filing system.  For example, the bugzilla filer uses the
       python-bugzilla module to communicate.  This module has its own Bug
       object.  So, BugzillaBug wraps that object.  Therefore, Bugs may be
       created out of existing BugzillaBugs or may create their own if
       necessary.

       Methods in this class should raise the following exceptions:

       CommunicationError -- For all problems communicating with the remote
                             bug filing system.
       ValueError         -- For all other operations where the client
                             supplied values are not correct (invalid
                             resolution, status, whiteboard, etc.).
    """
    def __init__(self, filer, bug=None, *args, **kwargs):
        """Create a new Bug instance.  It is recommended that subclasses
           override this method to add extra attributes.

           filer        -- A reference to a Filer object used when performing
                           certain operations.  This may be None if it is not
                           required by the Filer or Bug objects.
           bug          -- If None, the filer-specific code should create a new
                           bug object.  Otherwise, the filer-specific code
                           should use the provided object as needed.
           args, kwargs -- If provided, these arguments should be passed as-is
                           when creating a new underlying bug object.  This
                           only makes sense if bug is not None.
        """
        self.filer = filer

    def __str__(self):
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError

    def addCC(self, address):
        """Add the provided email address to this bug.  This method must be
           provided by all subclasses, and return some non-None value on
           success.
        """
        raise NotImplementedError

    def addcomment(self, comment):
        """Add the provided comment to this bug.  This method must be provided
           by all subclasses, and return some non-None value on success.
        """
        raise NotImplementedError

    def attachfile(self, file, description, **kwargs):
        """Attach the filename given by file, with the given description, to
           this bug.  If provided, the given kwargs will be passed along to
           the Filer when attaching the file.  These args may be useful for
           doing things like setting the MIME type of the file.  This method
           must be provided by all subclasses and return some non-None value
           on success.
        """
        raise NotImplementedError

    def close(self, resolution, dupeid=0, comment=''):
        """Close this bug with the given resolution, optionally closing it
           as a duplicate of the provided dupeid and with the optional comment.
           resolution must be a value accepted by the Filer.  This method must
           be provided by all subclasses and return some non-None value on
           success.
        """
        raise NotImplementedError

    def id(self):
        """Return this bug's ID number.  This method must be provided by all
           subclasses.
        """
        raise NotImplementedError

    def setstatus(self, status, comment=''):
        """Set this bug's status and optionally add a comment.  status must be
           a value accepted by the Filer.  This method must be provided by all
           subclasses and return some non-None value on success.
        """
        raise NotImplementedError

    def setassignee(self, assigned_to='', reporter='', comment=''):
        """Assign this bug to the person given by assigned_to, optionally
           changing the reporter and attaching a comment.  assigned_to must be
           a valid account in the Filer.  This method must be provided by all
           subclasses and return some non-None value on success.
        """
        raise NotImplementedError

    def getwhiteboard(self, which=''):
        """Get the given whiteboard from this bug and return it.  Not all bug
           filing systems support the concept of whiteboards, so this method
           is optional.  Currently, anaconda does not call it.
        """
        return ""

    def appendwhiteboard(self, text, which=''):
        """Append the given text to the given whiteboard.  Not all bug filing
           systems support the concept of whiteboards, so this method is
           optional.  If provided, it should return some non-None value on
           success.  Currently, anaconda does not call this method.
        """
        return True

    def prependwhitebaord(self, text, which=''):
        """Put the given text at the front of the given whiteboard.  Not all
           bug filing systems support the concept of whiteboards, so this
           method is optional.  If provided, it should return some non-None
           value on success.  Currently, anaconda does not call this method.
        """
        return True

    def setwhiteboard(self, text, which=''):
        """Set the given whiteboard to be the given text.  Not all bug filing
           systems support the concept of whiteboards, so this method is
           optional.  If provided, it should return some non-None value on
           success.  Currently, anaconda does not call this method.
        """
        return True


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

    def __init__(self, bugUrl=None, develVersion=None, defaultProduct=None):
        AbstractFiler.__init__(self, bugUrl=bugUrl, develVersion=develVersion,
                               defaultProduct=defaultProduct)
        self._bz = None

    def login(self, username, password):
        import bugzilla

        self._bz = bugzilla.Bugzilla(url=self.bugUrl)

        retval = self._bz.login(username, password)
        if not retval:
            raise LoginError(self.bugUrl, username)

        return retval

    def createbug(self, *args, **kwargs):
        whiteboards = []

        for (key, val) in kwargs.items():
            if key.endswith("_whiteboard"):
                wb = key.split("_")[0]
                whiteboards.append((wb, val))
                kwargs.pop(key)

            if key == "platform":
                platformLst = self.__withBugzillaDo(lambda b: b._proxy.Bug.legal_values({'field': 'platform'}))
                if not val in platformLst['values']:
                    kwargs[key] = platformLst['values'][0]

        bug = self.__withBugzillaDo(lambda b: b.createbug(**kwargs))
        for (wb, val) in whiteboards:
            bug.setwhiteboard(val, which=wb)

        return BugzillaBug(self, bug=bug)

    def getbug(self, id):
        return BugzillaBug(self, bug=self.__withBugzillaDo(lambda b: b.getbug(id)))

    def getbugs(self, idlist):
        lst = self.__withBugzillaDo(lambda b: b.getbugs(idlist))
        return map(lambda b: BugzillaBug(self, bug=b), lst)

    def getproduct(self, prod):
        details = self.__withBugzillaDo(lambda b: b.getproducts())
        for d in details:
            if d['name'] == prod:
                return prod

        if self.defaultProduct:
            return self.defaultProduct
        else:
            raise ValueError, "The product %s is not valid and no defaultProduct is set." % prod

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
