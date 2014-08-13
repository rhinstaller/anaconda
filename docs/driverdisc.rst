Brief description of DriverDisc version 3
==========================================

For a new major release we decided to introduce a new version of DriverDisc
feature to ensure the smoothest vendor and user experience possible. We had
many reasons for it:

- the old DD didn't support multiple architectures
- the old DD wasn't particulary easy to create
- the old DD had two copys of modules, one for anaconda and one for
  instalation
- the modules in old DD weren't checked for kernel version

We also changed the feature internal code to enable some functionality that
was missing from the old version. More about it below.


Devices which can contain DDs
-----------------------------

The best place to save your DriverDisc to is USB flash device. We also support
(or plan to) IDE and SATA block devices with or without partitions, DriverDisc
image stored on block device, initrd overlay (see documentation below) and for
special cases even network retrieval of DriverDisc image.


What can be updated using DDs?
------------------------------

All drivers for block devices, which weren't used for retrieving DriverDiscs,
the same applies also for network drivers eg. you cannot upgrade network
driver for device, which was used prior the DriverDisc extraction.

RPMs for installation. If the DriverDisc repo contains newer package, than the
official repository, the newer package will get used.

We also plan to support anaconda's updates.img placement on the DriverDisc to
update stage2 behaviour of anaconda.


Selecting DD manually
---------------------

Use the 'inst.dd' kernel command line option to trigger DD mode.
If no argument is specified, the UI will prompt for the location of the driver
rpm. Otherwise, the rpm will be fetched from the specified location.

Please consult the appropriate Installer Guide for further information.


Automatic DriverDisc detection
------------------------------

Anaconda automatically looks for driverdiscs during startup.

The DriverDisc has to be on partition or filesystem which has been labeled
with 'OEMDRV' label.


DDv3 structure
--------------

The new DriverDisc format uses simple layout which can be created on top of
any anaconda's supported filesystem (vfat, squashfs, ext2 and ext3).

::

    /
    |rhdd3   - DD marker, contains the DD's description string
    /rpms
      |  /i386 - contains RPMs for this arch and acts as Yum repo
      |  /i586
      |  /x86_64
      |  /ppc
      |  /...  - any other architecture the DD provides drivers for

There is a special requirement for the RPMs used to update drivers. Anaconda
picks up only RPMs which provide "kernel-modules = <running kernel version>".


Initrd overlay driverdisc image
-------------------------------

We have designed another possible way of providing updates in network boot
environments. It is possible to update all modules this way, so if special
storage module (which gets used early) needs to be updated, this is the
preffered way.

This kind of driverdisc image is applied over the standard initrd and so has
to respect some rules.

- All updated modules belong to /lib/modules/<kernel version>/..  according to
  their usual location
- All new modules belong to /lib/modules/<kernel version>/updates
- All new firmware files belong to /lib/firmware
- The rpm repo with updated packages belongs to /tmp/DD-initrd/
- The (empty) trigger file /.rundepmod must be present


Firmware and module update
--------------------------

The firmware files together with all .ko files from the RPMs are exploded to
special module location, which has preference over built-in Anaconda modules.

Anaconda doesn't use built-in modules (except some storage modules needed for
the DD to function properly) during the DriverDisc mode, so even in case when
you are updating some modules with second (or later) DriverDisc, the updated
modules will be loaded. There is one exception though, if your module depends
on a module which is only present in built-in module directory, that built-in
module gets also loaded.


Package installation
--------------------

It is also possible to include arbitrary packages on the DriverDisc media and
mark them for installation. You just have to include the package name in the
Yum repo for correct architecture and mark it as mandatory.


Summary
-------

This new DriverDisc format should simplify the DD creation and usage a lot. We
will gladly hear any comments as this is partially still work in progress.
