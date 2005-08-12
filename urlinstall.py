#
# urlinstall.py - URL based install source method
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from hdrlist import groupSetFromCompsFile, HeaderList
from installmethod import InstallMethod, FileCopyException
import os
import rpm
import time
import string
import struct
import socket
import urlgrabber.grabber as grabber

from snack import *
from constants import *

from rhpl.translate import _

# we import these explicitly because urllib loads them dynamically, which
# stinks -- and we need to have them imported for the --traceonly option
import ftplib
import httplib
import StringIO

import logging
log = logging.getLogger("anaconda")

FILENAME = 1000000
DISCNUM  = 1000002

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
    def readCompsViaMethod(self, hdlist):
	fname = self.findBestFileMatch(None, 'comps.xml')
	# if not local then assume its on host
	if fname is None:
	    fname = '%s/%s/base/comps.xml' % (self.baseUrl, productPath)
	    log.warning("Comps not in update dirs, using %s",fname)
        return groupSetFromCompsFile(fname, hdlist)

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

    def getRPMFilename(self, h, timer, callback=None):

	fullPath = "/%s/RPMS/%s" % (productPath, h[FILENAME])

	return self.getFilename(fullPath, callback=callback, disc = h[DISCNUM])

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

    def readHeaders(self):
	hdurl = "%s/%s/base/hdlist" % (self.baseUrl, productPath)

	try:
	    url = grabber.urlopen (hdurl, retry = 5)
	except grabber.URLGrabError, e:
	    log.critical ("URLGrabError: %s occurred getting %s", e.strerror,
			    hdurl)
	    raise FileCopyException

	raw = url.read(16)
	if raw is None or len(raw) < 1:
	    raise TypeError, "header list is empty!"
	
	hl = []
	while (raw and len(raw)>0):
	    info = struct.unpack("iiii", raw)
	    magic1 = socket.ntohl(info[0]) & 0xffffffffL
	    if (magic1 != 0x8eade801L or info[1]):
		raise TypeError, "bad magic in header"

	    il = socket.ntohl(info[2])
	    dl = socket.ntohl(info[3])
	    totalSize = il * 16 + dl;
	    hdrString = raw[8:] + url.read(totalSize)
	    hdr = rpm.headerLoad(hdrString)
	    hl.append(hdr)

	    raw = url.read(16)

	return HeaderList(hl)

    def mergeFullHeaders(self, hdlist):
	fn = self.getFilename("%s/base/hdlist2" % (productPath,), callback=None)
	hdlist.mergeFullHeaders(fn)
	os.unlink(fn)

    def setIntf(self, intf):
	self.intf = intf

    def __init__(self, url, rootPath, intf):
	InstallMethod.__init__(self, url, rootPath, intf)

        if url.startswith("ftp"):
            isFtp = 1
        else:
            isFtp = 0

        # build up the url.  this is tricky so that we can replace
        # the first instance of // with /%3F to do absolute URLs right
        i = string.index(url, '://') + 3
        self.baseUrl = url[:i]
        rem = url[i:]

        i = string.index(rem, '/') + 1
        self.baseUrl = self.baseUrl + rem[:i]
        rem = rem[i:]
        
        # encoding fun so that we can handle absolute paths
        if rem.startswith("/") and isFtp:
            rem = "%2F" + rem[1:]

        self.baseUrl = self.baseUrl + rem

        if self.baseUrl[-1] == "/":
            self.baseUrl = self.baseUrl[:-1]

	# self.baseUrl points at the path which contains the 'product'
	# directory with the hdlist.

	if self.baseUrl[-6:] == "/disc1":
	    self.multiDiscs = 1
	    self.pkgUrl = self.baseUrl[:-6]
	else:
	    self.multiDiscs = 0
	    self.pkgUrl = self.baseUrl
	
