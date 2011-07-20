# sshd.py
# Configuring the sshd daemon from Anaconda.
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#


import logging
import os, sys
log = logging.getLogger("anaconda")

import iutil
import users
from flags import flags

def createSshKey(algorithm, keyfile):
    path = '/etc/ssh/%s' % (keyfile,)
    argv = ['-q','-t',algorithm,'-f',path,'-C','','-N','']
    if os.access(path, os.R_OK):
        return
    log.debug("running \"%s\"" % (" ".join(['ssh-keygen']+argv),))

    so = "/tmp/ssh-keygen-%s-stdout.log" % (algorithm,)
    se = "/tmp/ssh-keygen-%s-stderr.log" % (algorithm,)
    iutil.execWithRedirect('ssh-keygen', argv, stdout=so, stderr=se)

def doSshd(anaconda):
    if flags.sshd:
        # we need to have a libuser.conf that points to the installer root for
        # sshpw, but after that we start sshd, we need one that points to the
        # install target.
        luserConf = users.createLuserConf(instPath="")
        handleSshPw(anaconda)
        startSsh()
        del(os.environ["LIBUSER_CONF"])
    else:
        log.info("sshd: not enabled, skipping.")

    users.createLuserConf(anaconda.rootPath)

def handleSshPw(anaconda):
    if not anaconda.ksdata:
        return

    u = users.Users(anaconda)

    userdata = anaconda.ksdata.sshpw.dataList()
    for ud in userdata:
        if u.checkUserExists(ud.username, root="/"):
            u.setUserPassword(username=ud.username, password=ud.password,
                              isCrypted=ud.isCrypted, lock=ud.lock)
        else:
            kwargs = ud.__dict__
            kwargs.update({"root": "/", "mkmailspool": False})
            u.createUser(ud.username, **kwargs)

    del u

def startSsh():
    if iutil.isS390():
        return

    if not iutil.fork_orphan():
        os.open("/var/log/lastlog", os.O_RDWR | os.O_CREAT, 0644)
        ssh_keys = {
            'rsa1':'ssh_host_key',
            'rsa':'ssh_host_rsa_key',
            'dsa':'ssh_host_dsa_key',
            }
        for (algorithm, keyfile) in ssh_keys.items():
            createSshKey(algorithm, keyfile)
        sshd = iutil.find_program_in_path("sshd")
        args = [sshd, "-f", "/etc/ssh/sshd_config.anaconda"]
        os.execv(sshd, args)
        sys.exit(1)
