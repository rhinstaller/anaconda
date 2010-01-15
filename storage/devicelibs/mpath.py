from ..udev import *

def parseMultipathOutput(output):
    # this function parses output from "multipath -d", so we can use its
    # logic for our topology.
    # The input looks like:
    # create: mpathb (1ATA     ST3120026AS                                         5M) undef ATA,ST3120026AS
    # size=112G features='0' hwhandler='0' wp=undef
    # `-+- policy='round-robin 0' prio=1 status=undef
    #   `- 2:0:0:0 sda 8:0  undef ready running
    # create: mpatha (36006016092d21800703762872c60db11) undef DGC,RAID 5
    # size=10G features='1 queue_if_no_path' hwhandler='1 emc' wp=undef
    # `-+- policy='round-robin 0' prio=2 status=undef
    #   |- 6:0:0:0 sdb 8:16 undef ready running
    #   `- 7:0:0:0 sdc 8:32 undef ready running
    #
    # (In anaconda, the first one there won't be included because we blacklist
    # "ATA" as a vendor.)
    #
    # It returns a structure like:
    # [ {'mpatha':['sdb','sdc']}, ... ]
    mpaths = {}

    name = None
    devices = []

    lines = output.split('\n')
    for line in lines:
        lexemes = line.split()
        if not lexemes:
            break
        if lexemes[0] == 'create:':
            if name and devices:
                mpaths.append(mpath)
                name = None
                devices = []
            name = lexemes[1]
        elif lexemes[0].startswith('size='):
            pass
        elif lexemes[0] == '`-+-':
            pass
        elif lexemes[0] in ['|-','`-']:
            devices.append(lexemes[2])
    
    if name and devices:
        mpaths[name] = devices

    return mpaths

def identifyMultipaths(devices):
    # this function does a couple of things
    # 1) identifies multipath disks
    # 2) sets their ID_FS_TYPE to multipath_member
    # 3) removes the individual members of an mpath's partitions
    # sample input with multipath pairs [sda,sdc] and [sdb,sdd]
    # [sr0, sda, sda1, sdb, sda2, sdc, sdd, sdc1, sdc2, sde, sde1]
    # sample output:
    # [sr0, sda, sdb, sdc, sdd, sde, sde1]

    log.info("devices to scan for multipath: %s" % [d['name'] for d in devices])
    serials = {}
    non_disk_devices = {}
    for d in devices:
        serial = udev_device_get_serial(d)
        if (not udev_device_is_disk(d)) or \
                (not d.has_key('ID_SERIAL_SHORT')):
            non_disk_devices.setdefault(serial, [])
            non_disk_devices[serial].append(d)
            log.info("adding %s to non_disk_device list" % (d['name'],))
            continue

        serials.setdefault(serial, [])
        serials[serial].append(d)

    singlepath_disks = []
    multipaths = []
    for serial, disks in serials.items():
        if len(disks) == 1:
            log.info("adding %s to singlepath_disks" % (disks[0]['name'],))
            singlepath_disks.append(disks[0])
        else:
            # some usb cardreaders use multiple lun's (for different slots)
            # and report a fake disk serial which is the same for all the
            # lun's (#517603)
            all_usb = True
            for d in disks:
                if d.get("ID_USB_DRIVER") != "usb-storage":
                    all_usb = False
                    break
            if all_usb:
                log.info("adding multi lun usb mass storage device to singlepath_disks: %s" %
                         [disk['name'] for disk in disks])
                singlepath_disks.extend(disks)
                continue

            for d in disks:
                log.info("adding %s to multipath_disks" % (d['name'],))
                d["ID_FS_TYPE"] = "multipath_member"

            multipaths.append(disks)
            log.info("found multipath set: [%s]" % [d['name'] for d in disks])

    for mpath in multipaths:
        for serial in [d['ID_SERIAL_SHORT'] for d in mpath]:
            if non_disk_devices.has_key(serial):
                log.info("filtering out non disk devices [%s]" % [d['name'] for d in non_disk_devices[serial]])
                del non_disk_devices[serial]

    partition_devices = []
    for devs in non_disk_devices.values():
        partition_devices += devs

    # this is the list of devices we want to keep from the original
    # device list, but we want to maintain its original order.
    singlepath_disks = filter(lambda d: d in devices, singlepath_disks)
    #multipaths = filter(lambda d: d in devices, multipaths)
    partition_devices = filter(lambda d: d in devices, partition_devices)

    mpathStr = "["
    for mpath in multipaths:
        mpathStr += str([d['name'] for d in mpath])
    mpathStr += "]"

    s = "(%s, %s, %s)" % ([d['name'] for d in singlepath_disks], \
                          mpathStr, \
                          [d['name'] for d in partition_devices])
    log.info("devices post multipath scan: %s" % s)
    return (singlepath_disks, multipaths, partition_devices)

class MultipathConfigWriter:
    def __init__(self):
        self.blacklist_devices = []
        self.mpaths = []

    def addBlacklistDevice(self, device):
        self.blacklist_devices.append(device)

    def addMultipathDevice(self, mpath):
        self.mpaths.append(mpath)

    def write(self):
        # if you add anything here, be sure and also add it to anaconda's
        # multipath.conf
        ret = ''
        ret += """\
# multipath.conf written by anaconda

defaults {
	user_friendly_names yes
}
blacklist {
	devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
	devnode "^hd[a-z]"
	devnode "^dcssblk[0-9]*"
	device {
		vendor "DGC"
		product "LUNZ"
	}
	device {
		vendor "IBM"
		product "S/390.*"
	}
	# don't count normal SATA devices as multipaths
	device {
		vendor  "ATA"
	}
	# don't count 3ware devices as multipaths
	device {
		vendor  "3ware"
	}
	device {
		vendor  "AMCC"
	}
	# nor highpoint devices
	device {
		vendor  "HPT"
	}
"""
        for device in self.blacklist_devices:
            if device.serial:
                ret += '\twwid %s\n' % device.serial
            elif device.vendor and device.model:
                ret += '\tdevice {\n'
                ret += '\t\tvendor %s\n' % device.vendor
                ret += '\t\tproduct %s\n' % device.model
                ret += '\t}\n'
        ret += '}\n'
        ret += 'multipaths {\n'
        for mpath in self.mpaths:
            ret += '\tmultipath {\n'
            for k,v in mpath.config.items():
                ret += '\t\t%s %s\n' % (k, v)
            ret += '\t}\n'
        ret += '}\n'

        return ret
