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

from comps import ComponentSet, HeaderList
from installmethod import InstallMethod
import os
import rpm
import time
import urllib
import string
import struct
import socket
from log import log

# we import these explicitly because urllib loads them dynamically, which
# stinks -- and we need to have them imported for the --traceonly option
import ftplib
import httplib
import StringIO

FILENAME = 1000000
DISCNUM  = 1000002

class UrlInstallMethod(InstallMethod):

    def readCompsViaMethod(self, hdlist):
	return ComponentSet(self.baseUrl + '/RedHat/base/comps', hdlist)

    def getFilename(self, h, timer):
	root = "/mnt/sysimage"
	pathlist = [ "/var/tmp", "/tmp",
		     "/." ]
	for p in pathlist:
	    if (os.access(root + p, os.X_OK)):
		tmppath = root + p
		break

	# h doubles as a filename -- gross
	if type("/") == type(h):
	    fullPath = self.baseUrl + "/" + h
	else:
	    if self.multiDiscs:
		base = "%s/disc%d" % (self.pkgUrl, h[DISCNUM])
	    else:
		base = self.pkgUrl

	    fullPath = base + "/RedHat/RPMS/" + h[FILENAME]

	file = tmppath + os.path.basename(fullPath)

        connected = 0
        while not connected:
            try:
                urllib.urlretrieve(fullPath, file)
            except IOError, (errnum, msg):
		log("IOError %s occured getting %s: %s",
			errnum, fullPath, str(msg))
                time.sleep(5)
            else:
                connected = 1
                
	return file

    def unlinkFilename(self, fullName):
	os.remove(fullName)

    def readHeaders(self):
        connected = 0
        while not connected:
            try:
                url = urllib.urlopen(self.baseUrl + "/RedHat/base/hdlist")
            except IOError, (errnum, msg):
		log("IOError %s occured getting %s: %s",
			errnum, self.baseUrl + "/RedHat/base/hdlist", msg)
                time.sleep(5)
            else:
                connected = 1
                
	raw = url.read(16)
	hl = []
	while (raw):
	    info = struct.unpack("iiii", raw)
	    magic1 = socket.ntohl(info[0]) & 0xffffffff
	    if (magic1 != 0x8eade801 or info[1]):
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
	fn = self.getFilename("RedHat/base/hdlist2", None)
	hdlist.mergeFullHeaders(fn)
	os.unlink(fn)

    def __init__(self, url):
	InstallMethod.__init__(self)

	i = string.index(url, '://') + 2
	self.baseUrl = url[0:i]
	rem = url[i:]
	new = string.replace(rem, "//", "/")
	while (new != rem):
	    rem = new
	    new = string.replace(rem, "//", "/")
	rem = new
        if rem and rem[-1] == "/":
            rem = rem[:-1]
	self.baseUrl = self.baseUrl + rem

	if self.baseUrl[-6:] == "/disc1":
	    self.multiDiscs = 1
	    self.pkgUrl = self.baseUrl[:-6]
	else:
	    self.multiDiscs = 0
	    self.pkgUrl = self.baseUrl
	    
