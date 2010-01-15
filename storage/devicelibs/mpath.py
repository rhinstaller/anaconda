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
        self.blacklist_exceptions = []
        self.mpaths = []

    def addMultipathDevice(self, mpath):
        for parent in mpath.parents:
            self.blacklist_exceptions.append(parent.name)
        self.mpaths.append(mpath)

    def write(self):
        ret = ""
        ret += """\
# multipath.conf written by anaconda

defaults {
	verbosity 2
}
blacklist {
	devnode "*"
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
	device {
		vendor "IBM"
		product "S/390.*"
	}
}
devices {
	device {
		vendor "COMPELNT"
		product "Compellent Vol"
		path_grouping_policy multibus
		path_checker tur
		checker tur
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "APPLE*"
		product "Xserve RAID "
		path_grouping_policy multibus
	}
	device {
		vendor "3PARdata"
		product "VV"
		path_grouping_policy multibus
	}
	device {
		vendor "DEC"
		product "HSG80"
		path_grouping_policy group_by_prio
		path_checker hp_sw
		checker hp_sw
		features "1 queue_if_no_path"
		hardware_handler "1 hp-sw"
		prio hp_sw
	}
	device {
		vendor "HP"
		product "A6189A"
		path_grouping_policy multibus
		no_path_retry 12
	}
	device {
		vendor "(COMPAQ|HP)"
		product "(MSA|HSV)1.0.*"
		path_grouping_policy group_by_prio
		path_checker hp_sw
		checker hp_sw
		features "1 queue_if_no_path"
		hardware_handler "1 hp-sw"
		prio hp_sw
		no_path_retry 12
		rr_min_io 100
	}
	device {
		vendor "HP"
		product "MSA VOLUME"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		prio alua
		failback immediate
		no_path_retry 12
		rr_min_io 100
	}
	device {
		vendor "(COMPAQ|HP)"
		product "HSV1[01]1|HSV2[01]0|HSV300|HSV4[05]0"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		prio alua
		failback immediate
		no_path_retry 12
		rr_min_io 100
	}
	device {
		vendor "HP"
		product "MSA2[02]12fc|MSA2012i"
		path_grouping_policy multibus
		path_checker tur
		checker tur
		failback immediate
		no_path_retry 18
		rr_min_io 100
	}
	device {
		vendor "HP"
		product "MSA2012sa|MSA23(12|24)(fc|i|sa)|MSA2000s VOLUME"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		prio alua
		failback immediate
		no_path_retry 18
		rr_min_io 100
	}
	device {
		vendor "HP"
		product "HSVX700"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		hardware_handler "1 alua"
		prio alua
		failback immediate
		no_path_retry 12
		rr_min_io 100
	}
	device {
		vendor "HP"
		product "LOGICAL VOLUME.*"
		path_grouping_policy multibus
		path_checker cciss_tur
		checker cciss_tur
		no_path_retry 12
	}
	device {
		vendor "DDN"
		product "SAN DataDirector"
		path_grouping_policy multibus
	}
	device {
		vendor "EMC"
		product "SYMMETRIX"
		path_grouping_policy multibus
		getuid_callout "/lib/udev/scsi_id --page=pre-spc3-83 --whitelisted --device=/dev/%n"
	}
	device {
		vendor "DGC"
		product ".*"
		product_blacklist "LUNZ"
		path_grouping_policy group_by_prio
		path_checker emc_clariion
		checker emc_clariion
		features "1 queue_if_no_path"
		hardware_handler "1 emc"
		prio emc
		failback immediate
		no_path_retry 60
	}
	device {
		vendor "FSC"
		product "CentricStor"
		path_grouping_policy group_by_serial
	}
	device {
		vendor "(HITACHI|HP)"
		product "OPEN-.*"
		path_grouping_policy multibus
		path_checker tur
		checker tur
	}
	device {
		vendor "HITACHI"
		product "DF.*"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
		prio hds
		failback immediate
	}
	device {
		vendor "IBM"
		product "ProFibre 4000R"
		path_grouping_policy multibus
	}
	device {
		vendor "IBM"
		product "1722-600"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "1 queue_if_no_path"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry 300
	}
	device {
		vendor "IBM"
		product "1724"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "1 queue_if_no_path"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry 300
	}
	device {
		vendor "IBM"
		product "1726"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "1 queue_if_no_path"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry 300
	}
	device {
		vendor "IBM"
		product "1742"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "IBM"
		product "1814"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "IBM"
		product "1815"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "IBM"
		product "1818"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "IBM"
		product "3526"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "IBM"
		product "3542"
		path_grouping_policy group_by_serial
		path_checker tur
		checker tur
	}
	device {
		vendor "IBM"
		product "2105800"
		path_grouping_policy group_by_serial
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
	}
	device {
		vendor "IBM"
		product "2105F20"
		path_grouping_policy group_by_serial
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
	}
	device {
		vendor "IBM"
		product "1750500"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
		prio alua
		failback immediate
	}
	device {
		vendor "IBM"
		product "2107900"
		path_grouping_policy multibus
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
	}
	device {
		vendor "IBM"
		product "2145"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
		prio alua
		failback immediate
	}
	device {
		vendor "IBM"
		product "S/390 DASD ECKD"
		product_blacklist "S/390.*"
		path_grouping_policy multibus
		getuid_callout "/sbin/dasd_id /dev/%n"
		features "1 queue_if_no_path"
	}
	device {
		vendor "IBM"
		product "S/390 DASD FBA"
		product_blacklist "S/390.*"
		path_grouping_policy multibus
		getuid_callout "/sbin/dasdinfo -u -b %n"
		features "1 queue_if_no_path"
	}
	device {
		vendor "IBM"
		product "IPR.*"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
		hardware_handler "1 alua"
		prio alua
		failback immediate
	}
	device {
		vendor "AIX"
		product "VDASD"
		path_grouping_policy multibus
		failback immediate
		no_path_retry 60
	}
	device {
		vendor "DELL"
		product "MD3000"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "1 queue_if_no_path"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
	}
	device {
		vendor "DELL"
		product "MD3000i"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "1 queue_if_no_path"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
	}
	device {
		vendor "NETAPP"
		product "LUN.*"
		path_grouping_policy group_by_prio
		features "1 queue_if_no_path"
		prio netapp
		failback immediate
		rr_min_io 128
	}
	device {
		vendor "IBM"
		product "Nseries.*"
		path_grouping_policy group_by_prio
		features "1 queue_if_no_path"
		prio netapp
		failback immediate
		rr_min_io 128
	}
	device {
		vendor "Pillar"
		product "Axiom.*"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		prio alua
	}
	device {
		vendor "SGI"
		product "TP9[13]00"
		path_grouping_policy multibus
	}
	device {
		vendor "SGI"
		product "TP9[45]00"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "SGI"
		product "IS.*"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "STK"
		product "OPENstorage D280"
		path_grouping_policy group_by_prio
		path_checker tur
		checker tur
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
	}
	device {
		vendor "SUN"
		product "(StorEdge 3510|T4)"
		path_grouping_policy multibus
	}
	device {
		vendor "PIVOT3"
		product "RAIGE VOLUME"
		path_grouping_policy multibus
		getuid_callout "/lib/udev/scsi_id --page=0x80 --whitelisted --device=/dev/%n"
		path_checker tur
		checker tur
		features "1 queue_if_no_path"
		rr_min_io 100
	}
	device {
		vendor "SUN"
		product "CSM200_R"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "SUN"
		product "LCSM100_[IF]"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry queue
	}
	device {
		vendor "(LSI|ENGENIO)"
		product "INF-01-00"
		path_grouping_policy group_by_prio
		path_checker rdac
		checker rdac
		features "2 pg_init_retries 50"
		hardware_handler "1 rdac"
		prio rdac
		failback immediate
		no_path_retry 15
	}
}
blacklist_exceptions {
"""
        for device in self.blacklist_exceptions:
            ret += "\tdevnode \"^%s$\"\n" % (device,)
        ret += """\
}

multipaths {
"""
        for mpath in self.mpaths:
            ret += "\tmultipath {\n"
            for k,v in mpath.config.items():
                ret += "\t\t%s %s\n" % (k, v)
            ret += "\t}\n\n"
        ret += "}\n"

        return ret
