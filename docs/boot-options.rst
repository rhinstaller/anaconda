Anaconda Boot Options
=====================

:Authors:
    Anaconda Developers <anaconda-devel@lists.fedoraproject.org>
    Will Woods <wwoods@redhat.com>
    Anne Mulhern <amulhern@redhat.com>


.. |dracutkernel| replace:: dracut.kernel(7)
.. _dracutkernel: http://www.kernel.org/pub/linux/utils/boot/dracut/dracut.html#dracutcmdline7

.. |dracutnet| replace:: the "Network" section of |dracutkernel|_
.. _dracutnet: http://www.kernel.org/pub/linux/utils/boot/dracut/dracut.html#_network

.. |dracutdebug| replace::  dracut "Troubleshooting" guide
.. _dracutdebug: http://www.kernel.org/pub/linux/utils/boot/dracut/dracut.html#_troubleshooting

.. |anacondawiki| replace:: Anaconda wiki
.. _anacondawiki: https://fedoraproject.org/wiki/Anaconda

.. |anacondalogging| replace:: Anaconda wiki logging page
.. _anacondalogging: https://fedoraproject.org/wiki/Anaconda/Logging

These are the boot options that are useful when starting Anaconda. For more
information refer to the appropriate Installation Guide for your release and
to the |anacondawiki|_.

Anaconda bootup is handled by dracut, so most of the kernel arguments handled
by dracut are also valid. See |dracutkernel|_ for details on those options.

Throughout this guide, installer-specific options are prefixed with
``inst`` (e.g. ``inst.ks``).

.. _repo:

Installation Source
-------------------

.. NOTE::
    An *installable tree* is a directory structure containing installer
    images, packages, and repodata. [#tree]_

    Usually this is either a copy of the DVD media (or loopback-mounted DVD
    image), or the ``<arch>/os/`` directory on the Fedora mirrors.

.. [#tree] an installable tree must contain a valid `.treeinfo` file
         for ``inst.repo`` or ``inst.stage2`` to work.

.. _inst.repo:

inst.repo
^^^^^^^^^

This gives the location of the *Install Source* - that is, the place where the
installer can find its images and packages. It can be specified in a few
different ways:

``inst.repo=cdrom``
    Search the system's CDROM drives for installer media. This is the default.

``inst.repo=cdrom:<device>``
    Look for installer media in the specified disk device.

``inst.repo=hd:<device>:<path>``
    Mount the given disk partition and install from ISO file on the given path.
    This installation method requires ISO file, which contains an installable tree.

``inst.repo=[http,https,ftp]://<host>/<path>``
    Look for an installable tree at the given URL.

``inst.repo=nfs:[<options>:]<server>:/<path>``
    Mount the given NFS server and path. Uses NFS version **3** by default.

    You can specify what version of the NFS protocol to use by adding ``nfsvers=X``
    to the `options`.

    This accepts not just an installable tree directory in the ``<path>`` element,
    but you can also specify an ``.iso`` file. That ISO file is then mounted and
    used as the installation tree. This is often used for simulating a standard
    DVD installation using a remote ``DVD.iso`` image.

.. _diskdev:

.. NOTE::
    Disk devices may be specified with any of the following forms:

    Kernel Device Name
        ``/dev/sda1``, ``sdb2``

    Filesystem Label
        ``LABEL=FLASH``, ``LABEL=Fedora``, ``CDLABEL=Fedora\x2023\x20x86_64``

    Filesystem UUID
        ``UUID=8176c7bf-04ff-403a-a832-9557f94e61db``

    Non-alphanumeric characters should be escaped with ``\xNN``, where
    'NN' is the hexidecimal representation of the character (e.g. ``\x20`` for
    the space character (' ').

.. inst.addrepo:

inst.addrepo
^^^^^^^^^^^^

Add additional repository which can be used as another *Installation Source*
next to the main repository (see `inst.repo`_). This option can be used multiple
times during one boot. This can be specified in a few different ways:

``inst.addrepo=REPO_NAME,[http,https,ftp]://<host>/<path>``
    Look for the installable tree at the given URL.

``inst.addrepo=REPO_NAME,nfs://<server>:/<path>``
    Look for the installable tree at the given nfs path. Note that there is a
    colon after the host. Anaconda passes everything after “nfs:// ” directly
    to the mount command instead of parsing URLs according to RFC 2224.

``inst.addrepo=REPO_NAME,file://<path>``
    Look for the installable tree at the given location in the installation
    environment. Beware, to be able to use this variant the repo needs to
    be mounted before Anaconda tries to use it (load available software groups).
    The main usage for this command is having multiple repositories on one
    bootable ISO and install both the main repo and additional repositories from
    this ISO. The path to the additional repositories will be then
    `/run/install/source/REPO_ISO_PATH`. Another solution can be to mount this repo
    directory in the `%pre` section in the kickstart file.
    NOTE: The path must be absolute and start with `/` so the final url starts
    with `file:///...`.

``inst.addrepo=REPO_NAME,hd:<device>:<path>``
    Mount the given `<device>` partition and install from ISO specified by the `<path>`.
    If the `<path>` is not specified Anaconda will look for the valid installation ISO
    on the `<device>`. This installation method requires ISO with a valid installable tree.
    For more detail how to specify `<device>` argument part please see `diskdev`_.

The `REPO_NAME` is name of the repository and it is a required part. The name will be
used in the installation process. These repositories will be used only during the
installation but they **will not** be installed to the installed system.

.. inst.noverifyssl:

inst.noverifyssl
^^^^^^^^^^^^^^^^

Prevents Anaconda from verifying the ssl certificate for all HTTPS connections
with an exception of the additional repositories added by kickstart (where
--noverifyssl can be set per repo). Newly created additional repositories will honor
this option.


.. inst.proxy:

inst.proxy
^^^^^^^^^^

``inst.proxy=PROXY_URL``

Use the given proxy settings when performing an installation from a
HTTP/HTTPS/FTP source.  The ``PROXY_URL`` can be specified like this:
``[PROTOCOL://][USERNAME[:PASSWORD]@]HOST[:PORT]``.

.. inst.stage2:

inst.stage2
^^^^^^^^^^^

This specifies the location to fetch only the installer runtime image;
packages will be ignored. Otherwise the same as `inst.repo`_.

.. inst.stage2.all:

inst.stage2.all
^^^^^^^^^^^^^^^

All locations of type http, https or ftp specified with inst.stage2 will
be used sequentially one by one until the image is fetched. Other locations
will be ignored.

In the following example, Anaconda will try to fetch the image at first from
``http://a``, then from ``http://b`` and finally from ``http://c``.

::

   inst.stage2=http://a inst.stage2=http://b inst.stage2=http://c inst.stage2.all

Without the boot option ``inst.stage2.all``, Anaconda will try to fetch the
image only from ``http://c``, as usual.

::

   inst.stage2=http://a inst.stage2=http://b inst.stage2=http://c

inst.dd
^^^^^^^

This specifies the location for driver rpms. May be specified multiple times.
Locations may be specified using any of the formats allowed for
`inst.repo`_.

inst.multilib
^^^^^^^^^^^^^

This sets dnf's multilib_policy to "all" (as opposed to "best").

.. kickstart:

Kickstart
---------

.. inst.ks:

inst.ks
^^^^^^^

Give the location of a kickstart file to be used to automate the install.
Locations may be specified using any of the formats allowed for `inst.repo`_.

For any format the ``<path>`` component defaults to ``/ks.cfg`` if it is omitted.

For NFS kickstarts, if the ``<path>`` ends in ``/``, ``<ip>-kickstart`` is added.

If ``inst.ks`` is used without a value, the installer will look for
``nfs:<next_server>:/<filename>``

* ``<next_server>`` is the DHCP "next-server" option, or the IP of the DHCP server itself
* ``<filename>`` is the DHCP "filename" option, or ``/kickstart/``, and
  if the filename given ends in ``/``, ``<ip>-kickstart`` is added (as above)

For example:

* DHCP server: ``192.168.122.1``
* client address: ``192.168.122.100``
* kickstart file: ``nfs:192.168.122.1:/kickstart/192.168.122.100-kickstart``

.. inst.ks.all:

inst.ks.all
^^^^^^^^^^^

Use all locations of type ``http``, ``https`` or ``ftp`` specified with
multiple ``inst.ks`` sequentially one by one until kickstart file is fetched.
Locations of other types (eg. ``nfs``) will be ignored.

Without this option, only last location specified by ``inst.ks`` is used.

In the following example, Anaconda will try to fetch the kickstart file at
first from ``http://a/a.ks``, then from ``http://b/b.ks`` and finally from
``http://c/c.ks``.

::

   inst.ks=http://a/a.ks inst.ks=http://b/b.ks inst.ks=http://c/c.ks inst.ks.all

Without the boot option ``inst.ks.all``, Anaconda will try to fetch the
kickstart file only from ``http://c/c.ks``, as usual.

::

   inst.ks=http://a/a.ks inst.ks=http://b/b.ks inst.ks=http://c/c.ks

.. inst.ks.sendmac:

inst.ks.sendmac
^^^^^^^^^^^^^^^

Add headers to outgoing HTTP requests which include the MAC addresses of all
network interfaces. The header is of the form:

* ``X-RHN-Provisioning-MAC-0: eth0 01:23:45:67:89:ab``

This is helpful when using ``inst.ks=http...`` to provision systems.

.. inst.ks.sendsn:

inst.ks.sendsn
^^^^^^^^^^^^^^

Add a header to outgoing HTTP requests which includes the system's serial
number. [#serial]_

The header is of the form:

* ``X-System-Serial-Number: <serial>``

.. [#serial] as read from ``/sys/class/dmi/id/product_serial``

.. inst.ksstrict:

inst.ksstrict
^^^^^^^^^^^^^^

With this option, all warnings from reading the kickstart file will be
treated as errors. They will be printed on the output and the installation
will terminate immediately.

By default, the warnings are printed to logs and the installation
continues.

Network Options
---------------

Initial network setup is handled by dracut. For detailed information consult
|dracutnet|.

The most common dracut network options are covered here, along with some
installer-specific options.

.. ip:

ip
^^

Configure one (or more) network interfaces. You can use multiple ``ip``
arguments to configure multiple interfaces, but if you do you must specify an
interface for every ``ip=`` argument, and you must specify which interface
is the primary boot interface with `bootdev`_.

Accepts a few different forms; the most common are:

.. ip=ibft:

``ip=<dhcp|dhcp6|auto6|ibft>``
    Try to bring up every interface using the given autoconf method.  Defaults
    to ``ip=dhcp`` if network is required by ``inst.repo``, ``inst.ks``, ``inst.updates``,
    etc.

``ip=<interface>:<autoconf>``
    Bring up only one interface using the given autoconf method, e.g.
    ``ip=eth0:dhcp``.

``ip=<ip>::<gateway>:<netmask>:<hostname>:<interface>:none``
    Bring up the given interface with a static network config, where:

        ``<ip>``
            The client IP address. IPv6 addresses may be specified by putting
            them in square brackets, like so: ``[2001:DB8::1]``.

        ``<gateway>``
            The default gateway. IPv6 addresses are accepted here too.

        ``<netmask>``
            The netmask (e.g. ``255.255.255.0``) or prefix (e.g. ``64``).

        ``<hostname>``
            Hostname for the client machine. This component is optional.

``ip=<ip>::<gateway>:<netmask>:<hostname>:<interface>:<autoconf>:<mtu>``
    Bring up the given interface with the given autoconf method, but override the
    automatically obtained IP/gateway/etc. with the provided values.

    Technically all of the items are optional, so if you want to use dhcp but also
    set a hostname you can use ``ip=::::<hostname>::dhcp``.

.. nameserver:

nameserver
^^^^^^^^^^

Specify the address of a nameserver to use. May be used multiple times.

.. bootdev:

bootdev
^^^^^^^

Specify which interface is the boot device. Required if multiple ``ip=``
options are used.

.. ifname:

ifname
^^^^^^

``ifname=<interface>:<MAC>``
    Assign the given interface name to the network device with the given MAC. May
    be used multiple times.

.. NOTE::

    Dracut applies ifname option (which might involve renaming the device with
    given MAC) in initramfs only if the device is activated in initramfs stage
    (based on ip= option). If it is not the case, installer still binds the
    current device name to the MAC by adding HWADDR setting to the ifcfg file of
    the device.

.. inst.dhcpclass:

inst.dhcpclass
^^^^^^^^^^^^^^

Set the DHCP vendor class identifier [#dhcpd]_. Defaults to ``anaconda-$(uname -srm)``.

.. [#dhcpd] ISC ``dhcpd`` will see this value as "option vendor-class-identifier".

.. inst.waitfornet:

inst.waitfornet
^^^^^^^^^^^^^^^

``inst.waitfornet=<TIMEOUT_IN_SECONDS>``
    Wait for network connectivity at the beginning of the second stage of
    installation (after switchroot from early initramfs stage when the installer
    process is run).

.. inst.net.noautodefault

inst.net.noautodefault
^^^^^^^^^^^^^^^^^^^^^^

Configures NetworkManager so that it does not create default automatic
connections, which are the wired connections created and activated for any
Ethernet device that does not have a connection configured. These connections
are created in installer environment by NetworkManager during its start in post
switch-root stage of installation and are passed also to installed system.

Console / Display Options
-------------------------

.. console:

console
^^^^^^^

This is a kernel option that specifies what device to use as the primary
console. For example, if your console should be on the first serial port, use
``console=ttyS0``.

You can use multiple ``console=`` options; boot messages will be displayed on
all consoles, but anaconda will put its display on the last console listed.

Implies `inst.text`_.

.. inst.lang:

inst.lang
^^^^^^^^^

Set the language to be used during installation. The language specified must
be valid for the ``lang`` kickstart command.


.. inst.geoloc:

inst.geoloc
^^^^^^^^^^^

Configure geolocation usage in Anaconda. Geolocation is used to pre-set
language and time zone.

``inst.geoloc=0``
    Disables geolocation.

``inst.geoloc=provider_fedora_geoip``
    Use the Fedora GeoIP API (default).

``inst.geoloc=provider_hostip``
    Use the Hostip.info GeoIP API.

.. inst.geoloc-use-with-ks

inst.geoloc-use-with-ks
^^^^^^^^^^^^^^^^^^^^^^^

Enable geolocation even during a kickstart installation (both partial and fully automatic).
Otherwise geolocation is only enabled during a fully interactive installation.

.. inst.keymap:

inst.keymap
^^^^^^^^^^^

Set the keyboard layout to use. The layout specified must be valid for use with
the ``keyboard`` kickstart command.

.. inst.cmdline:

inst.cmdline
^^^^^^^^^^^^

Run the installer in command-line mode. This mode does not
allow any interaction; all options must be specified in a kickstart file or
on the command line.

.. inst.graphical:

inst.graphical
^^^^^^^^^^^^^^

Run the installer in graphical mode. This is the default.

.. inst.text:

inst.text
^^^^^^^^^

Run the installer using a limited text-based UI. Unless you're using a
kickstart file this probably isn't a good idea; you should use VNC instead.

.. inst.noninteractive

inst.noninteractive
^^^^^^^^^^^^^^^^^^^

Run the installer in a non-interactive mode. This mode does not allow any
user interaction and can be used with graphical or text mode. With text
mode it behaves the same as the ``inst.cmdline`` mode.

.. inst.resolution:

inst.resolution
^^^^^^^^^^^^^^^

Specify screen size for the installer. Use format nxm, where n is the
number of horizontal pixels, m the number of vertical pixels. The lowest
supported resolution is 800x600.

.. inst.rdp:

inst.rdp
^^^^^^^^

Enable Remote Desktop Protocol-controlled installation. You will need to connect to
the machine using an RDP client application. An RDP install implies that the installed
system will boot up in in multiuser.target instead of to the graphical login screen.

Multiple RDP clients can connect.

When using ``inst.rdp``, you also need to set RDP username and password using the
``inst.rdp.username`` and ``inst.rdp.password`` boot options.

.. inst.rdp.username:

inst.rdp.username
^^^^^^^^^^^^^^^^^

Set username for the RDP session. To enable RDP access, also use the
``inst.rdp`` and ``inst.rdp.password`` boot options.

.. inst.rdp.password:

inst.rdp.password
^^^^^^^^^^^^^^^^^

Set password for the RDP session. To enable RDP access, also use the
``inst.rdp`` and ``inst.rdp.username`` boot options.

.. inst.xdriver:

inst.xdriver
^^^^^^^^^^^^

Specify the X driver that should be used during installation and on the
installed system.

This boot options is deprecated and has no effect.

.. inst.usefbx

inst.usefbx
^^^^^^^^^^^

Use the framebuffer X driver (``fbdev``) rather than a hardware-specific driver.

Equivalent to ``inst.xdriver=fbdev``.


This boot options is deprecated and has no effect.

.. inst.xtimeout:

inst.xtimeout
^^^^^^^^^^^^^

Specify the timeout in seconds for starting X server.

.. inst.sshd:

inst.sshd
^^^^^^^^^

Start up ``sshd`` during system installation. You can then ssh in while the
installation progresses to debug or monitor its progress.

.. CAUTION::
    The ``root`` account has no password by default. You can set one using
    the ``sshpw`` kickstart command.


Debugging and Troubleshooting
-----------------------------

.. inst.debug:

inst.debug
^^^^^^^^^^

Run the installer in the debugging mode.

.. inst.rescue:

inst.rescue
^^^^^^^^^^^

Run the rescue environment. This is useful for trying to diagnose and fix
broken systems.

.. inst.updates:

inst.updates
^^^^^^^^^^^^

Give the location of an ``updates.img`` to be applied to the installer runtime.
Locations may be specified using any of the formats allowed for ``inst.repo``.

For any format the ``<path>`` component defaults to ``/updates.img`` if it is
omitted.

.. inst.nokill:

inst.nokill
^^^^^^^^^^^

A debugging option that prevents anaconda from and rebooting when a fatal error
occurs or at the end of the installation process.

.. inst.noshell:

inst.noshell
^^^^^^^^^^^^

Do not put a shell on tty2 during install.

.. inst.notmux:

inst.notmux
^^^^^^^^^^^

Do not use tmux during install. This allows for output to get generated without
terminal control characters and is really meant for non-interactive uses.

.. inst.syslog:

inst.syslog
^^^^^^^^^^^

``inst.syslog=<host>[:<port>]``
    Once installation is running, send log messages to the syslog process on
    the given host. The default port is 514 (UDP).

    Requires the remote syslog process to accept incoming connections.

.. inst.virtiolog:

inst.virtiolog
^^^^^^^^^^^^^^

Forward logs through the named virtio port (a character device at
``/dev/virtio-ports/<name>``).

If not provided, a port named ``org.fedoraproject.anaconda.log.0``
will be used by default, if found.

See the |anacondalogging|_ for more info on setting up logging via virtio.

.. inst.wait_for_disks:

inst.wait_for_disks
^^^^^^^^^^^^^^^^^^^

Because disks can take some time to appear, an additional delay of 5 seconds
has been added.  This can be overridden by boot argument
`inst.wait_for_disks=<value>` to let dracut wait up to <value> additional
seconds (0 turns the feature off, causing dracut to only wait up to 500ms).
Alternatively, if the `OEMDRV` device is known to be present but too slow to be
autodetected, the user can boot with an argument like `inst.dd=hd:LABEL=OEMDRV`
to indicate that dracut should expect an `OEMDRV` device and not start the
installer until it appears.

This functionality could be used to load kickstart and driverdisks.


Boot loader options
-------------------

.. inst.extlinux:

inst.extlinux
^^^^^^^^^^^^^

Use extlinux as the bootloader. Note that there's no attempt to validate that
this will work for your platform or anything; it assumes that if you ask for it,
you want to try.

.. inst.sdboot:

inst.sdboot
^^^^^^^^^^^^^

Use systemd-boot as the bootloader. Note that there's no attempt to validate that
this will work for your platform or anything; it assumes that if you ask for it,
you want to try.

Note that this works only for package-based installations, where the bootloader can be chosen at
install time. For live images, this can work only if the live image was built with systemd-boot
instead of grub.

.. inst.leavebootorder:

inst.leavebootorder
^^^^^^^^^^^^^^^^^^^

Boot the drives in their existing order, to override the default of booting into
the newly installed drive on Power Systems servers and EFI systems. This is
useful for systems that, for example, should network boot first before falling
back to a local boot.

Storage options
---------------

.. inst.disklabel:

inst.disklabel
^^^^^^^^^^^^^^

Prefer creation of the specified disk label type. Specify ``gpt`` to prefer creation of GPT disk
labels. Specify ``mbr`` to prefer creation of MBR disk labels if supported.

.. inst.gpt:

inst.gpt
^^^^^^^^

Prefer creation of GPT disk labels. This option is deprecated and will be removed in future
releases. Use ``inst.disklabel=gpt`` instead.


Other options
-------------

.. inst.selinux:

inst.selinux
^^^^^^^^^^^^

Enable SELinux usage in the installed system (default). Note that when used as a
boot option, "selinux" and "inst.selinux" are not the same. The "selinux" option
is picked up by both the kernel and Anaconda, but "inst.selinux" is processed
only by Anaconda. So when "selinux=0" is used, SELinux will be disabled both in
the installation environment and in the installed system, but when
"inst.selinux=0" is used SELinux will only be disabled in the installation environment.
Also note that while SELinux is running in the installation environment by
default, it is running in permissive mode so disabling it there does not make
much sense.

.. inst.nosave

inst.nosave
^^^^^^^^^^^

Controls what installation results should not be saved to the installed system,
valid values are: "input_ks", "output_ks", "all_ks", "logs" and "all".

``input_ks``
    Disables saving of the input kickstart (if any).

``output_ks``
    Disables saving of the output kickstart generated by Anaconda.

``all_ks``
    Disables saving of both input and output kickstarts.

``logs``
    Disables saving of all installation logs.

``all``
    Disables saving of all kickstarts and all logs.

Multiple values can be combined as a comma separated list, for example: ``input_ks,logs``

.. NOTE::
    The nosave option is meant for excluding files from the installed system that *can't*
    be removed by a kickstart %post script, such as logs and input/output kickstarts.

.. inst.nonibftiscsiboot

inst.nonibftiscsiboot
^^^^^^^^^^^^^^^^^^^^^

Allows to place boot loader on iSCSI devices which were not configured in iBFT.

Profile options
^^^^^^^^^^^^^^^

Use the ``inst.profile`` option to specify a configuration profile. The installer will be
customized based on configuration files from ``/etc/anaconda/profile.d`` that are specific
for this profile.

.. inst.profile:

inst.profile
++++++++++++

Specify a profile id of a configuration profile. The id should match the ``profile_id`` option
of a configuration file in ``/etc/anaconda/profile.d``.

For example: ``inst.profile=fedora-server``

Third-party options
^^^^^^^^^^^^^^^^^^^

Since Fedora 19 the Anaconda installer supports third-party extensions called
*addons*. The *addons* can support their own set of boot options which should be
documented in their documentation or submitted here.

.. inst.kdump_addon:

inst.kdump_addon
++++++++++++++++

``inst.kdump_addon=on/off``

Enable kdump anaconda addon to setup the kdump service.


Deprecated Options
------------------

These options should still be accepted by the installer, but they are
deprecated and may be removed soon.

.. dns:

dns
^^^

Use `nameserver`_ instead. Note that ``nameserver`` does not
accept comma-separated lists; use multiple ``nameserver`` options instead.

.. netmask:
.. gateway:
.. hostname:

netmask, gateway, hostname
^^^^^^^^^^^^^^^^^^^^^^^^^^

These can be provided as part of the `ip`_ option.

ip=bootif
^^^^^^^^^

A PXE-supplied BOOTIF option will be used automatically, so there's no need

.. ksdevice:

ksdevice
^^^^^^^^

*Not present*
    The first device with a usable link is used

``ksdevice=link``
    Ignored (this is the same as the default behavior)

``ksdevice=bootif``
    Ignored (this is the default if ``BOOTIF=`` is present)

``ksdevice=ibft``
    Replaced with ``ip=ibft``. See `ip`_

``ksdevice=<MAC>``
    Replaced with ``BOOTIF=${MAC/:/-}``

``ksdevice=<DEV>``
    Replaced with `bootdev`_

Removed Options
---------------

These options are obsolete and have been removed.

.. askmethod:
.. asknetwork:

askmethod, asknetwork
^^^^^^^^^^^^^^^^^^^^^
Anaconda's initramfs is now is completely non-interactive, so these have been
removed.

Instead, use `inst.repo`_ or specify appropriate `Network Options`_.

.. serial:

.. blacklist:
.. nofirewire:

blacklist, nofirewire
^^^^^^^^^^^^^^^^^^^^^

``modprobe`` handles adding kernel modules to a denylist on its own; try
``modprobe.blacklist=<mod1>,<mod2>...``

You can add the firewire module to a denylist with ``modprobe.blacklist=firewire_ohci``.

method:
^^^^^^

Use `inst.repo`_ instead.

serial
^^^^^^

This option was never intended for public use; it was supposed to be used to
force anaconda to use ``/dev/ttyS0`` as its console when testing it on a live
machine.

Use ``console=ttyS0`` or similar instead. See `console`_ for details.

.. updates:

updates
^^^^^^^

Use `inst.updates`_ instead.

.. essid:
.. wepkey:
.. wpakey:

essid, wepkey, wpakey
^^^^^^^^^^^^^^^^^^^^^

Dracut doesn't support wireless networking, so these don't do anything.

.. ethtool:

ethtool
^^^^^^^

Who needs to force half-duplex 10-base-T anymore?

.. gdb:

gdb
^^^

This was used to debug ``loader``, so it has been removed. There are plenty of
options for debugging dracut-based initramfs - see the |dracutdebug|.

.. inst.loglevel:

inst.loglevel
^^^^^^^^^^^^^

The log level is always set to ``debug``.

.. inst.mediacheck:

inst.mediacheck
^^^^^^^^^^^^^^^

Use the dracut option rd.live.check instead.

ks=floppy
^^^^^^^^^

We no longer support floppy drives. Try ``inst.ks=hd:<device>`` instead.

.. inst.display:

display
^^^^^^^

For remote display of the UI, use `inst.rdp`_.

.. utf8:

utf8
^^^^

All this option actually did was set ``TERM=vt100``. The default ``TERM`` setting
works fine these days, so this was no longer necessary.

.. noipv6:

noipv6
^^^^^^

ipv6 is built into the kernel and can't be removed by anaconda.

You can disable ipv6 with ``ipv6.disable=1``. This setting will be carried onto
the installed system.

.. upgradeany:

upgradeany
^^^^^^^^^^

Anaconda doesn't handle upgrades anymore.

.. inst.repo for installable tree:

inst.repo=hd:<device>:<path> for installable tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda can't use this option with installable tree but only with an ISO file.

.. inst.zram:

inst.zram
^^^^^^^^^

Anaconda doesn't run ``zram.service`` anymore. See ``zram-generator`` for more information.

.. inst.singlelang:

inst.singlelang
^^^^^^^^^^^^^^^

Anaconda does not support single language mode anymore.

repo=nfsiso:...
^^^^^^^^^^^^^^^

Anaconda no longer needs explicit specification that an NFS location is an ISO image.
The difference between an installable tree and a dir with an ``.iso`` file is now
automatically detected, so this is the same as ``inst.repo=nfs:``...

.. inst.nodmraid:

inst.nodmraid
^^^^^^^^^^^^^

Anaconda no longer supports dmraid, BIOS/Firmware RAID devices are now handled by
``mdadm``.

.. inst.nompath:

inst.nompath
^^^^^^^^^^^^

This was used to disable support for multipath devices. Anaconda did not
support proper multipath disabling for a long time, the only thing this did
was disable parts of GUI.

.. inst.product:

inst.product
^^^^^^^^^^^^

Use the ``inst.profile`` option instead.

.. inst.variant:

inst.variant
^^^^^^^^^^^^

Use the ``inst.profile`` option instead.
.. inst.vnc:

inst.vnc
^^^^^^^^

Anaconda no longer supports VNC for remote display of the UI.
Instead, use ``inst.rdp`` for Remote Desktop Protocol (RDP) support.

.. inst.vncpassword:

inst.vncpassword
^^^^^^^^^^^^^^^^

Anaconda no longer supports VNC for remote display of the UI.
Use ``inst.rdp.password`` and related boot options instead.

.. inst.vncconnect:

inst.vncconnect
^^^^^^^^^^^^^^^

Anaconda no longer supports VNC for remote display of the UI.
