#
# urlinstall.py - URL based install source method
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from installmethod import InstallMethod, FileCopyException
import os
import time
import string
import struct
import socket
import urlparse
import urlgrabber.grabber as grabber

from snack import *
from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

def urlretrieve(location, file, callback=None):
    """Downloads from location and saves to file."""
    if callback is not None:
	callback(_("Connecting..."), 0)

    try:
	url = grabber.urlopen(location)
    except grabber.URLGrabError, e:
	raise IOError (e.errno, e.strerror)

    # see if there is a size
    try:
	filesize = int(url.info()["Content-Length"])
	if filesize == 0:
	    filesize = None
    except:
	filesize = None

    # create output file
    f = open(file, 'w+')

    # if they dont want a status callback just do it in one big swoop
    if callback is None:
	f.write(url.read())
    else:
	buf = url.read(65535)
	tot = len(buf)
	while len(buf) > 0:
	    if filesize is not None:
		callback("downloading", "%3d%%" % ((100*tot)/filesize,))
	    else:
		callback("downloading", "%dKB" % (tot/1024,))
	    f.write(buf)
	    buf = url.read(65535)
	    tot += len(buf)

    f.close()
    url.close()

class UrlInstallMethod(InstallMethod):

    def badPackageError(self, pkgname):
        return _("The file %s cannot be opened.  This is due to a missing "
                 "file or perhaps a corrupt package.  Please verify your "
                 "mirror contains all required packages, and try using a "
                 "different one.\n\n"
                 "If you reboot, your system will be left in an inconsistent "
                 "state that will likely require reinstallation.\n\n") % pkgname

    def getFilename(self, filename, callback=None, destdir=None, retry=1,
                    disc = 1):

	if destdir is None:
	    tmppath = self.getTempPath()
	else:
	    tmppath = destdir

        if self.multiDiscs:
            base = "%s/disc%d" %(self.pkgUrl, disc)
        else:
            base = self.pkgUrl
        
	fullPath = base + "/" + filename

	file = tmppath + "/" + os.path.basename(fullPath)

        tries = 0
        while tries < 5:
            try:
                rc=urlretrieve(fullPath, file, callback=callback)
            except IOError, (errnum, msg):
		log.critical("IOError %s occurred getting %s: %s"
                             %(errnum, fullPath.replace("%", "%%"), str(msg)))

		if not retry:
		    raise FileCopyException
		
                time.sleep(5)
            else:
                break

	    tries = tries + 1

        if tries >= 5:
            raise FileCopyException

	return file

    def copyFileToTemp(self, filename):
        tmppath = self.getTempPath()

        if self.multiDiscs:
            base = "%s/disc1" % (self.pkgUrl,)
        else:
            base = self.pkgUrl
	    
        fullPath = base + "/" + filename

        file = tmppath + "/" + os.path.basename(fullPath)

        tries = 0
        while tries < 5:
            try:
                urlretrieve(fullPath, file)
            except IOError, (errnum, msg):
		log.critical("IOError %s occurred getting %s: %s",
			     errnum, fullPath.replace("%", "%%"), str(msg))
                time.sleep(5)
            else:
                break
            tries = tries + 1

        if tries >= 5:
            raise FileCopyException
	return file

    def unlinkFilename(self, fullName):
	os.remove(fullName)

    def setIntf(self, intf):
	self.intf = intf

    def getMethodUri(self):
        return self.baseUrl

    def __init__(self, url, rootPath, intf):
	InstallMethod.__init__(self, url, rootPath, intf)

        (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)

	try:
            socket.inet_pton(socket.AF_INET6, netloc)
            netloc = '[' + netloc + ']'
        except:
            pass

        # encoding fun so that we can handle absolute paths
        if path[1] == '/' and scheme == 'ftp':
            path = "/%2F" + path[1:]

        self.baseUrl = urlparse.urlunsplit((scheme,netloc,path,query,fragid))

        # FIXME: does not work
#	# self.baseUrl points at the path which contains the 'product'
#	# directory with the hdlist.
#
#	if self.baseUrl[-6:] == "/disc1":
#	    self.multiDiscs = 1
#	    self.pkgUrl = self.baseUrl[:-6]
#	else:
#	    self.multiDiscs = 0
#	    self.pkgUrl = self.baseUrl
	
