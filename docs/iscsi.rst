iSCSI and Anaconda
==================

:Authors:
   Ales Kozumplik <akozumpl@redhat.com>

Introduction
------------

iSCSI device is a SCSI device connected to your computer via a TCP/IP
network. The communication can be handled either in hardware or in software, or
as a hybrid --- part software, part hardware.

The terminology:

- 'initiator', the client in the iscsi connection. The computer we are running
  Anaconda on is typically an initiator.
- 'target', the storage device behind the Network. This is where the data is
  physically stored and read from. You can turn any Fedora/RHEL machine to a
  target (or several) via scsi-target-utils.
- 'HBA' or Host Bus Adapter. A device (PCI card typically) you connect to a
  computer. It acts as a NIC and if you configure it properly it transparently
  connects to the target when started and all you can see is a block device on
  your system.
- 'software initiator' is what you end up with if you emulate most of what HBA is
  doing and just use a regular NIC for the iscsi communication. The modern Linux
  kernel has a software initiator. To use it, you need the Open-ISCSI software
  stack [1, 2] installed. It is known as iscsi-initiator-utils in Fedora/RHEL.
- 'partial offload card'. Similar to HBA but needs some support from kernel and
  iscsi-initiator-utils. The least pleasant to work with, particularly because
  there is no standardized amount of the manual setting that needs to be done
  (some connect to the target just like HBAs, some need you to bring their NIC
  part up manually etc.). Partial offload cards exist to get better performing
  I/O with less processor load than with software initiator.
- 'iBFT' as in 'Iscsi Boot Firmware Table'. A table in the card's bios that
  contains its network and target settings. This allows the card to configure
  itself, connect to a target and boot from it before any operating system or a
  bootloader has the chance. We can also read this information from
  /sys/firmware/ibft after the system starts and then use it to bring the card
  up (again) in Linux.
- 'CHAP' is the authentication used for iSCSI connections. The authentication
  can happen during target discovery or target login or both. It can happen in
  both directions too: the initiator authenticates itself to the target and the
  target is sometimes required to authenticate itself to the initiator.


What is expected from Anaconda
------------------------------

We are expected to:

- use an HBA like an ordinary disk. It is usually smart enough to bring itself
  up during boot, connect to the target and just act as an ordinary disk.
- allow creating new software initiator connections in the UI, both IPv4 and IPv6.
- facilitate bringing up iBFT connections for partial offload cards.
- install the root and/or /boot filesystems on any iSCSI initiator known to us
- remember to install dracut-network if we are booting from an iSCSI initiator that
  requires iscsi-initiator-utils in the ramdisk (most of them do)
- boot from an iSCSI initiator using dracut, this requires generating an
  appropriate set of kernel boot arguments for it [3].


How Anaconda handles iscsi
--------------------------

iSCSI comes into play several times while Anaconda does its thing:

In loader, when deciding what NIC we should setup, we check if we have iBFT
information from one of the cards. If we do we set that card up with what we
found in the table, it usually boils down to an IPv4 static or IPv4
DHCP-obtained address. [4][5]

Next, after the main UI startup during filtering (or storage scan, whatever
comes first) we startup the iscsi support code in Anaconda [6]. This currently
involves:
- manually modprobing related kernel modules
- starting the iscsiuio daemon (required by some partial offload cards)
- most importantly, starting the iscsid daemon

All iBFT connections are brought up next by looking at the cards' iBFT data, if
any. The filtering screen has a feature to add advanced storage devices,
including iSCSI. Both connection types are handled by libiscsi (see below). The
brought up iSCSI devices appear as /dev/sdX and are treated as ordinary block
devices.

When DeviceTree scans all the block devices it uses the udev data (particularly
the ID_BUS and ID_PATH keys) to decide if the device is an iscsi disk. If it is,
it is represented with an iScsiDiskDevice class instance. This helps Anaconda
remember that:

- we need to install dracut-network so the generated dracut image is able to
  bring up the underlying NIC and establish the iscsi connection.
- if we are booting from the device we need to pass dracut a proper set of
  arguments that will allow it to do so.


Libiscsi
--------

How are iSCSI targets found and logged into? Originally Anaconda was just
running iscsiadm as an external program through execWithRedirect(). This
ultimately proved awkward especially due to the difficulties of handling the
CHAP passphrases this way. That is why Hans de Goede <hdegoede@redhat.com>, the
previous maintainer of the Anaconda iscsi subsystem decided to write a better
interface and created libiscsi (do not confuse this with the libiscsi.c in
kernel). Currently libiscsi lives as a couple of patches in the RHEL6
iscsi-initiator-utils CVS (and in Fedora package git, in somewhat outdated
version). Since Anaconda is libiscsi's only client at the moment it is
maintained by the Anaconda team.

The promise of libiscsi is to provide a simple C/Python API to handle iSCSI
connections while being somewhat stable and independent of the changes in the
underlying initiator-utils (while otherwise being tied to it on the
implementation level).

And at the moment libiscsi does just that. It has a set of functions to discover
and login to targets software targets. It supports making connections through
partial offload interfaces, but the only discovery method supported at this
moment is through firmware (iBFT). Its public data structures are independent of
iscsi-initiator-utils. And there is some python boilerplate that wraps the core
functions so we can easily call those from Anaconda.

To start nontrivial hacking on libiscsi prepare to spend some time familiarizing
yourself with the iscsi-initiator-utils internals (it is complex but quite
nice).


Debugging iSCSI bugs
--------------------

There is some information in anaconda.log and storage.log but libiscsi itself is
quite bad at logging. Most times useful information can be found by sshing onto
the machine and inspecting the output of different iscsiadm commands [2][7],
especially querying the existing sessions and known interfaces.

If for some reason the DeviceTree fails at recognizing iscsi devices as such,
'udevadm info --exportdb' is of interest.

The booting problems are either due to incorrectly generated dracut boot
arguments or they are simply dracut bugs.

Note that many of the iscsi adapters are installed in different Red Hat machines
and so the issues can often be reproduced and debugged.


Future of iSCSI in Anaconda
---------------------------

- extend libiscsi to allow initializing arbitrary connections from a partial
  offload card. Implement the Anaconda UI to utilize this. Difficulty hard.
- extend libiscsi with device binding support. Difficulty hard.
- work with iscsi-initiator-utils maintainer to get libiscsi.c upstream and then
  to rawhide Fedora. Then the partial offload patches in the RHEL6 Anaconda can
  be migrated there too and partial offload can be tested. This is something
  that needs to be done before RHEL7. Difficulty medium.
- improve libiscsi's logging capabilities. Difficulty easy.

.. [1] http://www.open-iscsi.org/
.. [2] /usr/share/doc/iscsi-initiator-utils-6.*/README
.. [3] man 7 dracut.kernel
.. [4] Anaconda git repository, anaconda/loader/ibft.c
.. [5] Anaconda git repository, anaconda/loader/net.c, chooseNetworkInterface()
.. [6] Anaconda git repository, anaconda/storage/iscsi.py
.. [7] 'man 8 iscsiadm'

