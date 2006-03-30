#
# users.py - user account install data
#
# Matt Wilson <msw@redhat.com>
# Brent Fox <bfox@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import random
import crypt
import os
import string

class Password:
    def __init__ (self):
        self.crypt = None
	self.pure = None

    def getPure(self):
	return self.pure

    def set (self, password, isCrypted = 0):
	if isCrypted:
	    self.crypt = password
	    self.pure = None
	else:
            salt = (random.choice (string.letters +
                                   string.digits + './') + 
                    random.choice (string.letters +
                                   string.digits + './'))
            self.crypt = crypt.crypt (password, salt)
	    self.pure = password

    def getCrypted(self):
	return self.crypt

class RootPassword(Password):
    def __repr__(self):
	return "<Type RootPassword>"

    def __str__(self):
	return "<Type RootPassword>"

    def write(self, instPath, useMD5):
	pure = self.getPure()
	if pure:
	    setPassword(instPath, "root", pure, useMD5)
	else:
	    setPassword(instPath, "root", self.getCrypted (), useMD5,
			alreadyCrypted = 1)

    def writeKS(self, f, useMD5):
        pure = self.getPure()
        if pure:
            f.write("rootpw --iscrypted %s\n" %(cryptPassword(pure, useMD5)))
        else:
            f.write("rootpw --iscrypted %s\n" %(self.getCrypted()))

def cryptPassword(password, useMD5):
    if useMD5:
	salt = "$1$"
	saltLen = 8
    else:
	salt = ""
	saltLen = 2

    for i in range(saltLen):
	salt = salt + random.choice (string.letters +
                                     string.digits + './')

    return crypt.crypt (password, salt)

def setPassword(instPath, account, password, useMD5, alreadyCrypted = 0):
    if not alreadyCrypted:
	password = cryptPassword(password, useMD5)

    devnull = os.open("/dev/null", os.O_RDWR)

    argv = [ "/usr/sbin/usermod", "-p", password, account ]
    iutil.execWithRedirect(argv[0], argv, root = instPath, 
			   stdout = '/dev/null', stderr = None)
    os.close(devnull)
