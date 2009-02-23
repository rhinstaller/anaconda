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
import tempfile
import os
import os.path

def createLuserConf(instPath, saltname='md5'):
    """Writes a libuser.conf for instPath."""
    if os.getenv("LIBUSER_CONF") and os.access(os.environ["LIBUSER_CONF"], os.R_OK):
        fn = os.environ["LIBUSER_CONF"]
        fd = open(fn, 'w')
    else:
        (fp, fn) = tempfile.mkstemp(prefix="libuser.")
        fd = os.fdopen(fp, 'w')

    buf = """
[defaults]
skeleton = %(instPath)s/etc/skel
mailspooldir = %(instPath)s/var/mail
crypt_style = %(salt)s
modules = files shadow
create_modules = files shadow
[files]
directory = %(instPath)s/etc
[shadow]
directory = %(instPath)s/etc
""" % {"instPath": instPath, "salt": saltname}

    fd.write(buf)
    fd.close()
    os.environ["LIBUSER_CONF"] = fn

# These are explained in crypt/crypt-entry.c in glibc's code.  The prefixes
# we use for the different crypt salts:
#     $1$    MD5
#     $5$    SHA256
#     $6$    SHA512
def cryptPassword(password, salt=None):
    salts = {'md5': '$1$', 'sha256': '$5$', 'sha512': '$6$', None: ''}
    saltstr = salts[salt]
    saltlen = 2

    if salt == 'md5' or salt == 'sha256' or salt == 'sha512':
        saltlen = 16

    for i in range(saltlen):
        saltstr = saltstr + random.choice (string.letters +
                                           string.digits + './')

    return crypt.crypt (password, saltstr)

class Users:
    def __init__ (self):
        self.admin = libuser.admin()

    def createUser (self, name, password=None, isCrypted=False, groups=[],
                    homedir=None, shell=None, uid=None, root="/mnt/sysimage",
                    salt=None):
        if self.admin.lookupUserByName(name):
            return None

        userEnt = self.admin.initUser(name)
        groupEnt = self.admin.initGroup(name)

        grpLst = filter(lambda grp: grp,
                        map(lambda name: self.admin.lookupGroupByName(name), groups))
        userEnt.set(libuser.GIDNUMBER, [groupEnt.get(libuser.GIDNUMBER)[0]] +
                    map(lambda grp: grp.get(libuser.GIDNUMBER)[0], grpLst))

        if not homedir:
            homedir = "/home/" + name

        # Do this to make the user's home dir under the install root.
        if homedir[0] != "/":
            userEnt.set(libuser.HOMEDIRECTORY, root + "/" + homedir)
        else:
            userEnt.set(libuser.HOMEDIRECTORY, root + homedir)

        if shell:
            userEnt.set(libuser.LOGINSHELL, shell)

        if uid >= 0:
            userEnt.set(libuser.UIDNUMBER, uid)

        self.admin.addUser(userEnt)
        self.admin.addGroup(groupEnt)

        if password:
            if isCrypted:
                self.admin.setpassUser(userEnt, password, True)
            else:
                self.admin.setpassUser(userEnt,
                                       cryptPassword(password, salt=salt),
                                       True)

        # Add the user to all the groups they should be part of.
        grpLst.append(self.admin.lookupGroupByName(name))
        for grp in grpLst:
            grp.add(libuser.MEMBERNAME, name)
            self.admin.modifyGroup(grp)

        # Now set the correct home directory to fix up passwd.
        userEnt.set(libuser.HOMEDIRECTORY, homedir)
        self.admin.modifyUser(userEnt)
        return True

    def setRootPassword(self, password, isCrypted, salt=None):
        rootUser = self.admin.lookupUserByName("root")

        if isCrypted:
            self.admin.setpassUser(rootUser, password, True)
        else:
            self.admin.setpassUser(rootUser, cryptPassword(password, salt=salt), True)

        self.admin.modifyUser(rootUser)
