#
# iutil.py - generic install utility functions
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, isys, string, stat
import signal
import os.path
from errno import *
import rhpl
import warnings
import subprocess
from flags import flags
from constants import *
from rhpl.translate import _
import re

import logging
log = logging.getLogger("anaconda")

def execWithRedirect(command, argv, stdin = 0, stdout = 1, stderr = 2,	
                     searchPath = 0, root = '/'):
    def chroot ():
        os.chroot(root)

        if not searchPath and not os.access (command, os.X_OK):
            raise RuntimeError, command + " can not be run"

    if type(stdin) == type("string"):
        if os.access(stdin, os.R_OK):
            stdin = open(stdin)
        else:
            stdin = 0
    if type(stdout) == type("string"):
        stdout = open(stdout, "w")
    if type(stderr) == type("string"):
        stderr = open(stderr, "w")

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin, stdout=stdout,
                                stderr=stderr, preexec_fn=chroot, cwd=root)
        ret = proc.wait()
    except OSError, (errno, msg):
        raise RuntimeError, "Error running " + command + ": " + msg

    return ret

def execWithCapture(command, argv, stdin = 0, stderr = 2, root='/'):
    def chroot():
        os.chroot(root)

    if type(stdin) == type("string"):
        if os.access(stdin, os.R_OK):
            stdin = open(stdin)
        else:
            stdin = 0
    if type(stderr) == type("string"):
        stderr = open(stderr, "w")

    try:
        pipe = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=stderr,
                                preexec_fn=chroot, cwd=root)
    except OSError, (errno, msg):
        raise RuntimeError, "Error running " + command + ": " + msg

    rc = pipe.stdout.read()
    pipe.wait()
    return rc

def execConsole():
    try:
        proc = subprocess.Popen(["/bin/sh"])
        proc.wait()
    except OSError, (errno, msg):
        raise RuntimeError, "Error running /bin/sh: " + msg

# return size of directory (and subdirs) in kilobytes
def getDirSize(dir):
    def getSubdirSize(dir):
	# returns size in bytes
        mydev = os.lstat(dir)[stat.ST_DEV]

        dsize = 0
        for f in os.listdir(dir):
	    curpath = '%s/%s' % (dir, f)
	    sinfo = os.lstat(curpath)
            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += getSubdirSize(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]
            else:
                pass

        return dsize
    return getSubdirSize(dir)/1024

# this is in kilobytes - returns amount of RAM not used by /tmp
def memAvailable():
    tram = memInstalled()

    ramused = getDirSize("/tmp")
    if os.path.isdir("/tmp/ramfs"):
        ramused += getDirSize("/tmp/ramfs")

    return tram - ramused

# this is in kilobytes
def memInstalled():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("MemTotal:"):
            fields = string.split(l)
            mem = fields[1]
            break

    return int(mem)

# try to keep 2.4 kernel swapper happy!
def swapSuggestion(quiet=0):
    mem = memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
	log.info("Detected %sM of memory", mem)
	
    if mem < 128:
        minswap = 96
        maxswap = 192
    else:
        if mem > 2000:
            minswap = 1000
            maxswap = 2000 + mem
        else:
            minswap = mem
            maxswap = 2*mem

    if not quiet:
	log.info("Swap attempt of %sM to %sM", minswap, maxswap)

    return (minswap, maxswap)

    
# this is a mkdir that won't fail if a directory already exists and will
# happily make all of the directories leading up to it. 
def mkdirChain(dir):
    try:
        os.makedirs(dir, 0755)
    except OSError, (errno, msg):
        try:
            if errno == EEXIST and stat.S_ISDIR(os.stat(dir).st_mode):
                return
        except:
            pass
            
        log.error("could not create directory %s: %s" % (dir, msg))

def swapAmount():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("SwapTotal:"):
            fields = string.split(l)
            return int(fields[1])
    return 0
        
def copyDeviceNode(src, dest):
    """Copies the device node at src to dest by looking at the type of device,
    major, and minor of src and doing a new mknod at dest"""

    filestat = os.lstat(src)
    mode = filestat[stat.ST_MODE]
    if stat.S_ISBLK(mode):
        type = stat.S_IFBLK
    elif stat.S_ISCHR(mode):
        type = stat.S_IFCHR
    else:
        # XXX should we just fallback to copying normally?
        raise RuntimeError, "Tried to copy %s which isn't a device node" % (src,)

    os.mknod(dest, mode | type, filestat.st_rdev)

# make the device-mapper control node
def makeDMNode(root="/"):
    major = minor = None

    for (fn, devname, val) in ( ("/proc/devices", "misc", "major"),
                                ("/proc/misc", "device-mapper", "minor") ):
        f = open(fn)
        lines = f.readlines()
        f.close()
        for line in lines:
            try:
                (num, dev) = line.strip().split(" ")
            except:
                continue
            if dev == devname:
                s = "%s = int(num)" %(val,)
                exec s
                break

#    print "major is %s, minor is %s" %(major, minor)
    if major is None or minor is None:
        return
    mkdirChain(root + "/dev/mapper")
    try:
        os.mknod(root + "/dev/mapper/control", stat.S_IFCHR | 0600,
               os.makedev(major, minor))
    except:
        pass

# make some miscellaneous character device nodes 
def makeCharDeviceNodes():
    for dev in ["input/event0", "input/event1", "input/event2", "input/event3"]:
        isys.makeDevInode(dev, "/dev/%s" % (dev,))

# make the device nodes for all of the drives on the system
def makeDriveDeviceNodes():
    hardDrives = isys.hardDriveDict()
    for drive in hardDrives.keys():
        if drive.startswith("mapper"):
            continue
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

        if drive.startswith("hd"):
            num = 32
        elif drive.startswith("dasd"):
            num = 4
        else:
            num = 15

        if (drive.startswith("cciss") or drive.startswith("ida") or
            drive.startswith("rd") or drive.startswith("sx8")):
            sep = "p"
        else:
            sep = ""

        for i in range(1, num):
            dev = "%s%s%d" % (drive, sep, i)
            isys.makeDevInode(dev, "/dev/%s" % (dev,))

    cdroms = isys.cdromList()
    for drive in cdroms:
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

    tapeDrives = isys.tapeDriveList()
    for drive in tapeDrives:
        # make all tape device variants (stX,stXl,stXm,stXa,nstX,nstXl,nstXm,nstXa)
        for prefix in ("", "n"):
            for postfix in ("", "l", "m", "a"):
                device = "%s%s%s" % (prefix, drive, postfix)
                isys.makeDevInode(device, "/dev/%s" % (device,))

    for mdMinor in range(0, 32):
        md = "md%d" %(mdMinor,)
        isys.makeDevInode(md, "/dev/%s" %(md,))

    # make the node for the device mapper
    makeDMNode()
    
# this is disgusting and I feel very dirty
def hasiSeriesNativeStorage():
    if rhpl.getArch() != "ppc":
        return

    f = open("/proc/modules", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if line.startswith("ibmsis"):
            return 1
        if line.startswith("ipr"):
            return 1

    return 0

# return the ppc machine variety type
def getPPCMachine():
    
    if rhpl.getArch() != "ppc":
        return 0
    
    machine = rhpl.getPPCMachine()
    if machine is None:
        log.warning("Unable to find PowerPC machine type")
    elif machine == 0:
        log.warning("Unknown PowerPC machine type: %s" %(machine,))

    return machine

# return the pmac machine id
def getPPCMacID():
    machine = None
    
    if rhpl.getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
      if line.find('machine') != -1:
        machine = line.split(':')[1]
        machine = machine.strip()
        return machine

    log.warning("No Power Mac machine id")
    return 0

# return the pmac generation
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']
    
    if rhpl.getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    gen = None
    for line in lines:
      if line.find('pmac-generation') != -1:
        gen = line.split(':')[1]
        break

    if gen is None:
        log.warning("Unable to find pmac-generation")

    for type in pmacGen:
      if gen.find(type) != -1:
          return type

    log.warning("Unknown Power Mac generation: %s" %(gen,))
    return 0

# return if pmac machine is it an iBook/PowerBook
def getPPCMacBook():
    if rhpl.getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(string.lower(line), 'book') == -1:
        return 1
    return 0

cell = None
def isCell():
    global cell
    if cell is not None:
        return cell

    cell = False
    if rhpl.getArch() != "ppc":
        return cell

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(line, 'Cell') == -1:
          cell = True

    return cell

mactel = None
# return True if this is one of the Intel-based Apple Macs
def isMactel():
    global mactel
    if mactel is not None:
        return mactel
    
    if rhpl.getArch() not in ("x86_64", "i386"):
        mactel = False
    elif not os.path.exists("/usr/sbin/dmidecode"):
        mactel = False
    else:
        buf = execWithCapture("/usr/sbin/dmidecode",
                              ["dmidecode", "-s", "system-manufacturer"])
        if buf.lower().find("apple") != -1:
            mactel = True
        else:
            mactel = False
    return mactel

efi = None
def isEfi():
    global efi
    if efi is not None:
        return efi

    if not os.path.exists("/sys/firmware/efi"):
        efi = False
    else:
        efi = True

    return efi

def cpuFeatureFlags():
    """Convenience function to get CPU feature flags from /proc/cpuinfo."""

    if rhpl.getArch() not in ("i386", "x86_64"):
        return False
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if not line.startswith("flags"):
            continue
        # get the actual flags
        flags = line[:-1].split(":", 1)[1]
        # and split them
        flst = flags.split(" ")
        return flst

    return []

def writeRpmPlatform(root="/"):
    import rhpl.arch

    if flags.test:
        return
    if os.access("%s/etc/rpm/platform" %(root,), os.R_OK):
        return
    if not os.access("%s/etc/rpm" %(root,), os.X_OK):
        os.mkdir("%s/etc/rpm" %(root,))

    myarch = rhpl.arch.canonArch

    # now allow an override with rpmarch=i586 on the command line (#101971)
    if flags.targetarch != None:
        myarch = flags.targetarch

    # now make the current install believe it, too
    rhpl.arch.canonArch = myarch            
        
    f = open("%s/etc/rpm/platform" %(root,), 'w+')
    f.write("%s-redhat-linux\n" %(myarch,))
    f.close()

    # FIXME: writing /etc/rpm/macros feels wrong somehow
    # temporary workaround for #92285
    if os.access("%s/etc/rpm/macros" %(root,), os.R_OK):
        return
    if not (myarch.startswith("ppc64") or
            myarch in ("s390x", "sparc64", "x86_64", "ia64")):
        return
    f = open("%s/etc/rpm/macros" %(root,), 'w+')
    f.write("%_transaction_color   3\n")
    f.close()

## Check to see if we are in a xen environment.
#
def inXen():
    if os.path.exists("/proc/xen/capabilities"):
        return True
    return False

## Check to see if we are in a vmware environment.
#
def inVmware():
    lspci = ["lspci", "-vvv"] # only the very verbose show the VMware stuff :)
    proc = subprocess.Popen(lspci, stdout = subprocess.PIPE)
    (out, err) = proc.communicate()
    if "VMware" in out:
        return True
    return False


def getScsiDeviceByWwpnLunid(wwpn, lunid):
    found = 0
    for tgt in os.listdir('/sys/class/fc_transport'):
        if tgt[:6] != "target":
            continue
        dir= '/sys/class/fc_transport/%s' % tgt
        f = open('%s/port_name' % dir, "r")
        tgt_wwpn = f.readline()
        tgt_wwpn = tgt_wwpn.rstrip("\n")
        if tgt_wwpn.startswith("0x"):
            tgt_wwpn = tgt_wwpn[2:]
        tgt_wwpn = tgt_wwpn.upper()
        f.close()
        ## check the first match only
        if tgt_wwpn == wwpn:
            found = 1
            break

    if found == 0:
        return ""

    scsi_hctl="%s:%s" % (tgt[6:], lunid)

    found = 0
    for tgt in os.listdir('/sys/block'):
        devf = '/sys/block/%s/device' % tgt
        if not os.path.exists(devf):
            continue
        devf = os.readlink(devf)
        devf = os.path.basename(devf)
        if devf == scsi_hctl:
            found = 1
            break
    if found == 0:
        tgt = ""
    return tgt

def writeReiplMethod(reipl_path, reipl_type):
    filename = "%s/reipl_type" % (reipl_path,)

    try:
        f = open(filename, "w")
    except Exception, e:
        message = "Error: On open, cannot set reIPL method to %s (%s: %s)" % (reipl_type,filename,e,)
        log.warning(message)
        raise Exception (message)

    try:
        f.write(reipl_type)
        f.flush()
    except Exception, e:
        message = "Error: On write, cannot set reIPL method to %s (%s: %s)" % (reipl_type,filename,e,)
        log.warning(message)
        raise Exception (message)

    try:
        f.close()
    except Exception, e:
        message = "Error: On close, cannot set reIPL method to %s (%s: %s)" % (reipl_type,filename,e,)
        log.warning(message)
        raise Exception (message)

def reIPLonCCW(iplsubdev, reipl_path):
    device = "<unknown>"

    try:
        iplbits = re.split ('([0-9]+)', iplsubdev)
        if len (iplbits) != 3:
            message = "Error: %s splits into %s but not like we expect" % (iplsubdev,iplbits,)
            log.warning(message)
            raise Exception (message)

        device = os.readlink("/sys/block/" + iplbits[0] + "/device").split('/')[-1]

        writeReiplMethod(reipl_path, 'ccw')

        try:
            f = open("%s/ccw/device" % (reipl_path,), "w")
            f.write(device)
            f.close()
        except Exception, e:
            message = "Error: Could not set %s as reIPL device (%s)" % (device,e,)
            log.warning(message)
            raise Exception (message)

        try:
            f = open("%s/ccw/loadparm" % (reipl_path,), "w")
            f.write("\n")
            f.close()
        except Exception, e:
            message = "Error: Could not reset loadparm (%s)" % (e,)
            log.warning(message)
            raise Exception (message)

        try:
            f = open("%s/ccw/parm" % (reipl_path,), "w")
            f.write("\n")
            f.close()
        except Exception, e:
            message = "Warning: Could not reset parm (%s)" % (e,)
            log.warning(message)
            # do NOT raise an exception since this might not exist or not be writable

    except Exception, e:
        try:
            message = e.args[0]
        except:
            message = e.__str__ ()
        return (message,
                (_("After shutdown, please perform a manual IPL from DASD device %s to continue "
                   "installation") % (device,)))

    return None

def reIPLonFCP(iplsubdev, reipl_path):
    fcpvalue = { "device": "<unknown>", "wwpn": "<unknown>", "lun": "<unknown>" }

    try:
        iplbits = re.split ('([0-9]+)', iplsubdev)
        if len (iplbits) != 3:
            message = "Error: %s splits into %s but not like we expect" % (iplsubdev,iplbits,)
            log.warning(message)
            raise Exception (message)

        syspath = "/sys/block/" + iplbits[0] + "/device"

        fcpprops = [ ("hba_id", "device"), ("wwpn", "wwpn"), ("fcp_lun", "lun") ]

        # Read in values to change.
        # This way, if we can't set FCP mode, we can tell the user what to manually reboot to.
        for (syspath_property, reipl_property) in fcpprops:
            try:
                f = open(syspath + "/" + syspath_property, "r")
                value = f.read().strip()
                fcpvalue[reipl_property] = value
                f.close()
            except Exception, e:
                message = "Error: reading FCP property %s for reIPL (%s)" % (syspath_property,e,)
                log.warning(message)
                raise Exception (message)

        writeReiplMethod(reipl_path, 'fcp')

        # Write out necessary parameters.
        for (syspath_property, reipl_property) in fcpprops:
            try:
                f = open("%s/fcp/%s" % (reipl_path, reipl_property,), "w")
                f.write(fcpvalue[reipl_property])
                f.close()
            except Exception, e:
                message = "Error: writing FCP property %s for reIPL (%s)" % (reipl_property,e,)
                log.warning(message)
                raise Exception (message)

        defaultprops = [ ("bootprog", "0"), ("br_lba", "0") ]

        # Write out default parameters.
        for (reipl_property, default_value) in defaultprops:
            try:
                f = open("%s/fcp/%s" % (reipl_path, reipl_property,), "w")
                f.write (default_value)
                f.close()
            except Exception, e:
                message = "Error: writing default FCP property %s for reIPL (%s)" % (reipl_property,e,)
                log.warning(message)
                raise Exception (message)

    except Exception, e:
        try:
            message = e.args[0]
        except:
            message = e.__str__ ()
        return (message,
                (_("After shutdown, please perform a manual IPL from FCP %(device)s with WWPN %(wwpn)s "
                   "and LUN %(lun)s to continue installation") % (fcpvalue)))

    return None

def reIPL(anaconda, loader_pid):
    instruction = _("After shutdown, please perform a manual IPL from the device "
                    "now containing /boot to continue installation")

    reipl_path = "/sys/firmware/reipl"

    iplfs = anaconda.id.fsset.getEntryByMountPoint("/boot")
    if iplfs is None:
        iplfs = anaconda.id.fsset.getEntryByMountPoint("/")

    if iplfs is None:
        message = _("Could not get information for mount point /boot or /")
        log.warning(message)
        return (message, instruction)

    try:
        ipldev = iplfs.device.device
    except:
        ipldev = None

    if ipldev is None:
        message = _("Error determining mount point type")
        log.warning(message)
        return (message, instruction)

    message = (_("The mount point /boot or / is on a disk that we are not familiar with"), instruction)
    if ipldev.startswith("dasd"):
        message = reIPLonCCW(ipldev, reipl_path)
    elif ipldev.startswith("sd"):
        message = reIPLonFCP(ipldev, reipl_path)

    # the final return is either None if reipl configuration worked (=> reboot),
    # or a two-item list with errorMessage and rebootInstr (=> shutdown)
    return message
