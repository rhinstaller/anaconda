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
import re
import time
import string
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

    def getFilename(self, filename, callback=None, destdir=None, retry=1):

	if destdir is None:
	    tmppath = self.getTempPath()
	else:
	    tmppath = destdir

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

    def __copyFileToTemp(self, baseurl, filename, raise404=False):
        tmppath = self.getTempPath()

        fullPath = baseurl + "/" + filename

        file = tmppath + "/" + os.path.basename(fullPath)

        tries = 0
        while tries < 5:
            try:
                urlretrieve(fullPath, file)
            except IOError, (errnum, msg):
                if errnum == 14 and 404 in msg and raise404:
                    raise
		log.critical("IOError %s occurred getting %s: %s",
			     errnum, fullPath.replace("%", "%%"), str(msg))
                time.sleep(5)
            else:
                break
            tries = tries + 1

        if tries >= 5:
            raise FileCopyException
	return file

    def copyFileToTemp(self, filename):
        return self.__copyFileToTemp(self.pkgUrl, filename)
    def unlinkFilename(self, fullName):
	os.remove(fullName)

    def setIntf(self, intf):
	self.intf = intf

    def getMethodUri(self):
        return self.baseUrl

    def switchMedia(self, mediano, filename=""):
        if self.splitmethod:
            self.baseUrl = self.baseUrls[mediano - 1]

    def __checkUrlForIsoMounts(self):
        # account for multiple mounted ISOs on loopback...bleh
        # assumes ISOs are mounted as AAAAN where AAAA is some alpha text
        # and N is an integer.  so users could have these paths:
        #     CD1, CD2, CD3
        #     disc1, disc2, disc3
        #     qux1, qux2, qux3
        # as long as the alpha text is consistent and the ints increment
        #
        # NOTE: this code is basically a guess. we don't really know if
        # they are doing a loopback ISO install, but make a guess and
        # shove all that at yum and hope for the best   --dcantrell

        discdir = os.path.basename(self.pkgUrl)
        alpharm = re.compile("^[^0-9]+")
        discnum = alpharm.sub("", discdir)

        try:
            discnum = int(discnum)

            stripnum = re.compile("%s$" % (discnum,))
            basepath = stripnum.sub("", self.pkgUrl)

            # add all possible baseurls
            discnum = 1
            baseurls = [] # self.pkgUrl ]
            while True:
                dirpath = "%s%s" % (basepath, discnum)

                try:
                    filename = self.__copyFileToTemp(dirpath, ".discinfo")
                    self.unlinkFilename(filename)
                except:
                    break

                log.debug("Adding baseurl: %s" % (dirpath,))
                baseurls.append("%s" % (dirpath,))
                try:
                    self.unlinkFilename(filename)
                except:
                    pass
                discnum += 1

            if len(baseurls) > 1:
                self.baseUrls = tuple(baseurls)
                self.splitmethod = True
        except ValueError:
            # we didn't figure out the user's dir naming scheme
            pass

    def __init__(self, url, rootPath, intf):
	InstallMethod.__init__(self, url, rootPath, intf)

        (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)

	try:
            socket.inet_pton(socket.AF_INET6, netloc)
            netloc = '[' + netloc + ']'
        except:
            pass

        # encoding fun so that we can handle absolute paths
        if scheme == "ftp" and path and path.startswith("//"):
            path = "/%2F" + path[1:]

        self.baseUrl = urlparse.urlunsplit((scheme,netloc,path,query,fragid))
        self.pkgUrl = self.baseUrl

        self.__checkUrlForIsoMounts()

        self.currentMedia = []
