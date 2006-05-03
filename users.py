#
# users.py:  Code for creating user accounts and setting the root password
#
# Chris Lumens <clumens@redhat.com>
#
# Copyright (c) 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import libuser
import string
import crypt
import random

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

class Users:
    def __init__ (self):
        self.admin = libuser.admin()

    def createUser (self, name, password=None, isCrypted=False, groups=[],
                    homedir=None, shell=None, uid=None):
        if self.admin.lookupUserByName(name):
            return None

        userEnt = self.admin.initUser(name)
        groupEnt = self.admin.initGroup(name)

        gidLst = map(lambda grp: grp.get(libuser.GIDNUMBER)[0],
                     filter(lambda grp: grp,
                            map(lambda name: self.admin.lookupGroupByName(name), groups)))
        gidLst.extend(groupEnt.get(libuser.GIDNUMBER))

        userEnt.set(libuser.GIDNUMBER, gidLst)

        if not homedir:
            homedir = "/home/" + name

        # Do this to make the user's home dir under the install root.
        userEnt.set(libuser.HOMEDIRECTORY, "/mnt/sysimage/" + homedir)

        if shell:
            userEnt.set(libuser.LOGINSHELL, shell)

        if uid >= 0:
            userEnt.set(libuser.UIDNUMBER, uid)

        self.admin.addUser(userEnt)
        self.admin.addGroup(groupEnt)

        if password:
            if isCrypted:
                self.admin.setpassUser(userEnt, password, isCrypted)
            else:
                self.admin.setpassUser(userEnt, cryptPassword(password, True), isCrypted)

        # Now set the correct home directory to fix up passwd.
        userEnt.set(libuser.HOMEDIRECTORY, homedir)
        self.admin.modifyUser(userEnt)

    def setRootPassword(self, password, isCrypted, useMD5):
        rootUser = self.admin.lookupUserByName("root")

        if isCrypted:
            self.admin.setpassUser(rootUser, password, True)
        else:
            self.admin.setpassUser(rootUser, cryptPassword(password, useMD5), True)

        self.admin.modifyUser(rootUser)
