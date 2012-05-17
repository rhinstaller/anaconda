#
# edd.py
# BIOS EDD data parsing functions
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Hans de Goede <hdegoede@redhat.com>
#            Ales Kozumplik <akozumpl@redhat.com>
#

import glob
import logging
import os
import re
import struct

log = logging.getLogger("storage")

re_host_bus = re.compile(r'^PCI\s*(\S*)\s*channel: (\S*)\s*$')
re_interface_scsi = re.compile(r'^SCSI\s*id: (\S*)\s*lun: (\S*)\s*$')
re_interface_ata = re.compile(r'^ATA\s*device: (\S*)\s*$')

class EddEntry(object):
    """ This object merely collects what the /sys/firmware/edd/* entries can
        provide.
    """
    def __init__(self, sysfspath):
        self.type = None

        self.ata_device = None
        self.channel = None
        self.mbr_signature = None
        self.pci_dev = None
        self.scsi_id = None
        self.scsi_lun = None
        self.sectors = None

        self.load(sysfspath)

    def __str__(self):
        return \
            "\ttype: %(type)s, ata_device: %(ata_device)s\n" \
            "\tchannel: %(channel)s, mbr_signature: %(mbr_signature)s\n" \
            "\tpci_dev: %(pci_dev)s, scsi_id: %(scsi_id)s\n" \
            "\tscsi_lun: %(scsi_lun)s, sectors: %(sectors)s" % self.__dict__

    def _read_file(self, filename):
        contents = None
        if os.path.exists(filename):
            with open(filename) as f:
                contents = f.read().rstrip()
        return contents

    def load(self, sysfspath):
        interface = self._read_file(os.path.join(sysfspath, "interface"))
        if interface:
            self.type = interface.split()[0]
            if self.type == "SCSI":
                match = re_interface_scsi.match(interface)
                self.scsi_id = int(match.group(1))
                self.scsi_lun = int(match.group(2))
            elif self.type == "ATA":
                match = re_interface_ata.match(interface)
                self.ata_device = int(match.group(1))

        self.mbr_signature = self._read_file(
            os.path.join(sysfspath, "mbr_signature"))
        sectors = self._read_file(os.path.join(sysfspath, "sectors"))
        if sectors:
            self.sectors = int(sectors)
        hbus = self._read_file(os.path.join(sysfspath, "host_bus"))
        if hbus:
            match = re_host_bus.match(hbus)
            if match:
                self.pci_dev = match.group(1)
                self.channel = int(match.group(2))
            else:
                log.warning("edd: can not match host_bus: %s" % hbus)

class EddMatcher(object):
    """ This object tries to match given entry to a disk device name.

        Assuming, heuristic analysis and guessing hapens here.
    """
    def __init__(self, edd_entry):
        self.edd = edd_entry

    def devname_from_pci_dev(self):
        name = None
        if self.edd.type == "ATA" and \
                self.edd.channel is not None and \
                self.edd.ata_device is not None:
            path = "/sys/devices/pci0000:00/0000:%(pci_dev)s/host%(chan)d/"\
                "target%(chan)d:0:%(dev)d/%(chan)d:0:%(dev)d:0/block" % {
                'pci_dev' : self.edd.pci_dev,
                'chan' : self.edd.channel,
                'dev' : self.edd.ata_device
                }
            if os.path.isdir(path):
                block_entries = os.listdir(path)
                if len(block_entries) == 1:
                    name = block_entries[0]
            else:
                log.warning("edd: directory does not exist: %s" % path)
        elif self.edd.type == "SCSI":
            pattern = "/sys/devices/pci0000:00/0000:%(pci_dev)s/virtio*/block" % \
                {'pci_dev' : self.edd.pci_dev}
            matching_paths = glob.glob(pattern)
            if len(matching_paths) != 1 or not os.path.exists(matching_paths[0]):
                return None
            block_entries = os.listdir(matching_paths[0])
            if len(block_entries) == 1:
                name = block_entries[0]
        return name

    def match_via_mbrsigs(self, mbr_dict):
        """ Try to match the edd entry based on its mbr signature.

            This will obviously fail for a fresh drive/image, but in extreme
            cases can also show false positives for randomly matching data.
        """
        for (name, mbr_signature) in mbr_dict.items():
            if mbr_signature == self.edd.mbr_signature:
                return name
        return None

def biosdev_to_edd_dir(biosdev):
    return "/sys/firmware/edd/int13_dev%x" % biosdev

def collect_edd_data():
    edd_data_dict = {}
    # the hard drive numbering starts at 0x80 (128 decimal):
    for biosdev in range(0x80, 0x80+16):
        sysfspath = biosdev_to_edd_dir(biosdev)
        if not os.path.exists(sysfspath):
            break
        edd_data_dict[biosdev] = EddEntry(sysfspath)
    return edd_data_dict

def collect_mbrs(devices):
    """ Read MBR signatures from devices.

        Returns a dict mapping device names to their MBR signatures. It is not
        guaranteed this will succeed, with a new disk for instance.
    """
    mbr_dict = {}
    for dev in devices:
        try:
            fd = os.open(dev.path, os.O_RDONLY)
            # The signature is the unsigned integer at byte 440:
            os.lseek(fd, 440, 0)
            mbrsig = struct.unpack('I', os.read(fd, 4))
            os.close(fd)
        except OSError as e:
            log.warning("edd: error reading mbrsig from disk %s: %s" %
                        (dev.name, str(e)))
            continue

        mbrsig_str = "0x%08x" % mbrsig
        # sanity check
        if mbrsig_str == '0x00000000':
            log.info("edd: MBR signature on %s is zero. new disk image?" % dev.name)
            continue
        else:
            for (dev_name, mbrsig_str_old) in mbr_dict.items():
                if mbrsig_str_old == mbrsig_str:
                    log.error("edd: dupicite MBR signature %s for %s and %s" %
                              (mbrsig_str, dev_name, dev.name))
                    # this actually makes all the other data useless
                    return {}
        # update the dictionary
        mbr_dict[dev.name] = mbrsig_str
    log.info("edd: collected mbr signatures: %s" % mbr_dict)
    return mbr_dict

def get_edd_dict(devices):
    """ Generates the 'device name' -> 'edd number' mapping.

        The EDD kernel module that exposes /sys/firmware/edd is thoroughly
        broken, the information there is incomplete and sometimes downright
        wrong. So after we mine out all useful information that the files under
        /sys/firmware/edd/int13_*/ can provide, we resort to heuristics and
        guessing. Our first attempt is, by looking at the device type int
        'interface', attempting to map pci device number, channel number etc. to
        a sysfs path, check that the path really exists, then read the device
        name (e.g 'sda') from there. Should this fail we try to match contents
        of 'mbr_signature' to a real MBR signature found on the existing block
        devices.
    """
    mbr_dict = collect_mbrs(devices)
    edd_entries_dict = collect_edd_data()
    global edd_dict
    for (edd_number, edd_entry) in edd_entries_dict.items():
        log.debug("edd: data extracted from 0x%x:\n%s" % (edd_number, edd_entry))
        matcher = EddMatcher(edd_entry)
        # first try to match through the pci dev etc.
        name = matcher.devname_from_pci_dev()
        # next try to compare mbr signatures
        if name:
            log.debug("edd: matched 0x%x to %s using pci_dev" % (edd_number, name))
        else:
            name = matcher.match_via_mbrsigs(mbr_dict)
            if name:
                log.info("edd: matched 0x%x to %s using MBR sig" % (edd_number, name))

        if name:
            old_edd_number = edd_dict.get(name)
            if old_edd_number:
                log.info("edd: both edd entries 0x%x and 0x%x seem to map to %s" %
                          (old_edd_number, edd_number, name))
                # this means all the other data can be confused and useless
                return {}
            edd_dict[name] = edd_number
            continue
        log.error("edd: unable to match edd entry 0x%x" % edd_number)
    return edd_dict

edd_dict = {}
