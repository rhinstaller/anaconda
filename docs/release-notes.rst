Release notes
=============

This document describes major installer-related changes in Fedora releases.

A guide on adding new entries is in the release documentation.

Fedora 41
#########

Changes in the graphical interface
----------------------------------

Changes in kickstart support
----------------------------

Deprecate RPM modularity module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Based on the discontinuation of RPM modularity in Fedora 39, we have decided to remove the
RPM modularity feature in Anaconda.  The 'module' kickstart command is no longer
functional but can still be included in the kickstart file. However, its presence will now
generate a warning.  In a future release, this command will be completely removed, and its
usage will result in an error.

See also:
    - https://issues.redhat.com/browse/RHELBU-2699
    - https://issues.redhat.com/browse/INSTALLER-3909
    - https://github.com/pykickstart/pykickstart/pull/487

Changes in Anaconda configuration files
---------------------------------------

Remote repository for Flatpaks after deployment are now configurable
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Currently when OSTree installation detects Flatpak repository in the installation media
these Flatpaks are deployed and the remote was hardcoded to remote Fedora. This remote is
then used for updating the Flatpaks after installation.

After this change Flatpak remote can be set by ``flatpak_remote`` key in the configuration
file.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5493

Architecture and hardware support changes
-----------------------------------------

NVMe Fabrics support
^^^^^^^^^^^^^^^^^^^^

Anaconda now recognizes NVMe Fabrics drives. These drives are now shown in the Advanced
Storage screen, together with further details.

See also:
    - https://github.com/rhinstaller/anaconda/pull/4514

Add RISC-V 64 support
^^^^^^^^^^^^^^^^^^^^^

Added extlinux support for RISC-V 64 and grub support for RISC-V 64 UEFI.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5198

General changes
---------------

Use the standalone ``crypt_r`` package for crypting passwords
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Python standard library ``crypt`` module was removed from Python 3.13+.  Use the
standalone ``crypt_r`` package maintained by the Fedora Python SIG instead.  Support for
``crypt`` still exists as a fallback, as ``crypt_r`` is not available in old RHELs and
Fedoras.

See also:
    - https://bugzilla.redhat.com/2276036
    - https://github.com/rhinstaller/anaconda/pull/5628

Do not create default network profiles for network port devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Traditionally Anaconda creates default persistent network profiles (ifcfg files or
keyfiles) for every supported wired network device. We would like to move towards creating
profiles only for devices explicitly configured by installer. As a step in this direction
do not create such files for devices used as ports of a virtual device (for example bond
device) configured by installer, unless they were explicitly configured separately (for
example in early stage from boot options).

See also:
    - https://issues.redhat.com/browse/RHEL-38451
    - https://github.com/rhinstaller/anaconda/pull/5703

Remove deprecation warnings for kernel boot options without prefix
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Removing the deprecation warnings for kernel boot options without ``inst.`` prefix. This
was left for a couple of releases to advise users to switch their options to use
``inst.*`` instead. We are now removing them to not warn as it should be always used
``inst.`` as prefix.

See also:
    - https://issues.redhat.com/browse/INSTALLER-2363
    - https://github.com/rhinstaller/anaconda/pull/5723/

Add ping command line tool to Anaconda Dracut image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes boot of the installer ISO will fail because remote source can't be reached, if
this happens, it can be hard to debug because of the limited toolset inside the Dracut
shell.  For these reasons, we are adding a ping command line tool which can help with
debugging.

See also:
    - https://issues.redhat.com/browse/RHEL-5719
    - https://github.com/rhinstaller/anaconda/pull/5500

Fedora 40
#########

Changes in the graphical interface
----------------------------------

Dir and image installations run only in the non-interactive text mode now
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda now requires a fully defined kickstart file for installations into a local image
(via the ``--image`` cmdline option) or a local directory (via the ``--dirinstall`` cmdline
option) and these installations can run only in a non-interactive text-based user interface.
The ``anaconda`` and ``livemedia-creator`` tools can be used for these types of installations
with the following changes:

- If a user requests a dir or image installation, Anaconda runs in the text mode.
- If the user doesn't specify a kickstart file, Anaconda reports an error and aborts.
- If the specified kickstart file is incomplete, Anaconda reports an error and aborts.
- All options for specifying the user interface are ignored.

See also:
    - https://fedoraproject.org/wiki/Changes/Anaconda_dir_and_image_installations_in_automated_text_mode
    - https://github.com/rhinstaller/anaconda/pull/5447

Remove support for additional repositories from GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The widget that allowed users to specify and edit additional repositories for the package
installation was removed from the "Installation Source" screen of the GTK-based graphical
user interface. Use the kickstart support or the ``inst.addrepo`` boot option to specify
additional repositories.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5448

Redesign the Time & Date spoke in GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The timezone map was removed from the Time & Date spoke in the GTK-based user interface
and the spoke was redesigned to accommodate the changes. The installer no longer depends
on the the ``libtimezonemap`` package.

See also:
    - https://github.com/rhinstaller/anaconda/issues/5404
    - https://github.com/rhinstaller/anaconda/discussions/5355

Remove support for the LUKS version selection from GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All widgets for the LUKS version selection were removed from the "Manual Partitioning"
screen of the GTK-based graphical user interface. The installer will use the ``luks2``
version by default for all new devices and keep the LUKS version of existing ones. Use
the kickstart support or Blivet GUI to select the LUKS version.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5395

Remove libgnomekbd
^^^^^^^^^^^^^^^^^^

The library used by Anaconda to display the keyboard preview widget,
was switched from libgnomekdb to Tecla.
libgnomekdb is stuck in GTK 3 and X11 (libxklavier).

See also:
    - https://github.com/rhinstaller/anaconda/pull/5417

Remove screenshot support
^^^^^^^^^^^^^^^^^^^^^^^^^

It was previously possible to take a screenshot of the
Anaconda GUI by pressing a global hotkey. This was
never widely advertised & rather hard to use for anything
useful, as it was also necessary to manually extract the
resulting screenshots from the installation environment.

Furthermore, with many installations happening in VMs,
it is usually more convenient to take a screenshot using
the VM software anyway.

By dropping screenshot support, we can remove dependency
on the ``keybinder3`` library as well as the necessary
screenshot code in the GUI.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5255

Changes in kickstart support
----------------------------

Remove support for NVDIMM namespaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All additional support for NVDIMM is being deprecated and removed, especially the support
for the namespace reconfiguration. However, namespaces configured in the block/storage mode
can be still used for the installation.

The ``nvdimm`` kickstart command is deprecated and will be removed in future releases.

See also:
    - https://github.com/storaged-project/blivet/pull/1172
    - https://github.com/pykickstart/pykickstart/pull/469
    - https://github.com/rhinstaller/anaconda/pull/5353

The installation program now correctly processes the proxy configuration (#2177219)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, the installation program did not correctly process the ``--proxy`` option of the
``url`` Kickstart command or ``inst.proxy`` kernel boot parameter. As a consequence, you could
not use the specified proxy to fetch the installation image. With this update, the issue
is fixed and proxy works as expected.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2177219
    - https://github.com/rhinstaller/anaconda/pull/4828

Remove and deprecate selected kickstart commands and options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following deprecated kickstart commands and options are removed:

- ``autostep``
- ``method``
- ``logging --level``
- ``repo --ignoregroups``

The following kickstart options are deprecated:

- ``timezone --isUtc``
- ``timezone --ntpservers``
- ``timezone --nontp``
- ``%packages --instLangs``
- ``%packages --excludeWeakdeps``

See also:
    - https://github.com/rhinstaller/anaconda/pull/5436
    - https://github.com/rhinstaller/anaconda/pull/5438
    - https://github.com/pykickstart/pykickstart/pull/475

Changes in Anaconda configuration files
---------------------------------------

Architecture and hardware support changes
-----------------------------------------

General changes
---------------

Remove the ``inst.nompath`` boot option
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``inst.nompath`` boot option was deprecated in Fedora 36. It is now marked as removed.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5439

Preliminary support for bootable ostree containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda can now correctly detect and use the bootupd bootloader used in
bootable ostree containers. When the installed container includes the ``bootupctl`` tool, it
is used instead of installing the ``grub2`` bootloader by Anaconda.

See also:
    - https://github.com/rhinstaller/anaconda/pull/5342

Discoverable GPT partitions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda now creates discoverable GPT partitions. This means that the partitions use correct
type UUIDs according to the Discoverable Partitions Specification.

This behavior can be controlled using the new ``gpt_discoverable_partitions`` configuration
option in the ``Storage`` section, which defaults to ``True``.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2178043
    - https://bugzilla.redhat.com/show_bug.cgi?id=2160074
    - https://github.com/rhinstaller/anaconda/pull/4974
    - https://uapi-group.org/specifications/specs/discoverable_partitions_specification/
    - https://www.freedesktop.org/software/systemd/man/systemd-gpt-auto-generator.html

Remove all support of the built-in help system
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support of the built-in help accessible from spokes and hubs of all user interfaces
is removed. The ``help_directory`` Anaconda configuration option is deprecated and removed.
The ``anaconda-user-help`` package will be deprecated and removed.

Anaconda will aim to make user interfaces self-descriptive and encourage users to use the
official documentation of specific Linux distributions available on-line.

See also:
    - https://docs.fedoraproject.org/en-US/fedora/latest/getting-started/
    - https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/
    - https://src.fedoraproject.org/rpms/anaconda-user-help/


Fedora 39
#########

Changes in the graphical interface
----------------------------------

Use keyboard layout configuration from the Live system
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Until now, users had to specify keyboard layout for the Live environment manually in Anaconda.
With this change, live system itself is responsible for the keyboard configuration and
Anaconda just reads the configuration from the live system for the installed system.

The live keyboard layout is used automatically only if the user does not specify it manually.
At this moment, only Gnome Shell environment is supported.

This is proper fix for https://bugzilla.redhat.com/show_bug.cgi?id=2016613 which was resolved
by a workaround in the past. It is also a step forward to resolve
https://bugzilla.redhat.com/show_bug.cgi?id=1955025.

See also:
    - https://github.com/rhinstaller/anaconda/pull/4976
    - https://bugzilla.redhat.com/show_bug.cgi?id=2016613
    - https://bugzilla.redhat.com/show_bug.cgi?id=1955025

Changes in kickstart support
----------------------------

New kickstart options to control DNS handling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are several new options for the ``network`` kickstart command to control handling of DNS:

- The ``--ipv4-dns-search`` and ``--ipv6-dns-search`` allow manual setting of DNS search
  domains. These options mirror their respective NetworkManager properties, for example::

      network --device ens3 --ipv4-dns-search example.com,custom-intranet-domain.biz (...)

- ``--ipv4-ignore-auto-dns`` and ``--ipv6-ignore-auto-dns`` allow ignoring DNS settings from
  DHCP. These options do not take any arguments.

All of these ``network`` command options must be used together with the ``--device`` option.

See also:
    - https://github.com/pykickstart/pykickstart/pull/431
    - https://github.com/rhinstaller/anaconda/pull/4519
    - https://bugzilla.redhat.com/show_bug.cgi?id=1656662

Changes in Anaconda configuration files
---------------------------------------

Deprecated configuration options are now removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following deprecated configuration file options are now removed:

- ``kickstart_modules``
- ``addons_enabled``

See also:
    - https://github.com/rhinstaller/anaconda/pull/4764

Allow to turn off geolocation for language selection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New ``Localization`` section with ``use_geolocation`` option is added to Anaconda
configuration. The option allows to turn off geolocation for language selection.

See also:
    - https://github.com/rhinstaller/anaconda/pull/4719

Architecture and hardware support changes
-----------------------------------------

Add support for compressed kernel modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Support for Driver Discs containing compressed kernel modules has been
added. Support for compressed kernel modules is limited to file extensions
.ko.bz2, .ko.gz, .ko.xz and .ko.zst.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2032638
    - https://github.com/rhinstaller/anaconda/pull/5041

Wait 5 secs during boot for OEMDRV devices (#2171811)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Because disks can take some time to appear, an additional delay of 5 seconds
has been added.  This can be overridden by boot argument
``inst.wait_for_disks=<value>`` to let dracut wait up to <value> additional
seconds (0 turns the feature off, causing dracut to only wait up to 500ms).
Alternatively, if the ``OEMDRV`` device is known to be present but too slow to be
autodetected, the user can boot with an argument like ``inst.dd=hd:LABEL=OEMDRV``
to indicate that dracut should expect an ``OEMDRV`` device and not start the
installer until it appears.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2171811
    - https://github.com/rhinstaller/anaconda/pull/4586

General changes
---------------

New Runtime module
^^^^^^^^^^^^^^^^^^

Anaconda now has a new D-Bus module called ``Runtime``. This module stores run-time
configuration of the installer and provides methods for the overall installer flow control.

Warning: This module must always run, or anaconda crashes. Users of the following
configuration file entries must adapt to this change:

- ``kickstart_modules``
- ``activatable_modules``
- ``forbidden_modules``
- ``optional_modules``

See also:
    - https://github.com/rhinstaller/anaconda/pull/4730

Make the EFI System Partition at least 500MiB in size
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The minimum size of the EFI System Partition (ESP) created by Anaconda has changed from 200 MiB to
500 MiB. The maximum size, which is used in most cases, remains at 600 MiB.

The reasons for this change include:
    - This partition is used to deploy firmware updates. These updates need free space of twice the
      SPI flash size, which will grow from 64 to 128 MiB in near future and make the current
      partition size too small.
    - The new minimum is identical with what Microsoft mandates OEMs allocate for the partition.

See also:
    - https://fedoraproject.org/wiki/Changes/BiggerESP
    - https://github.com/rhinstaller/anaconda/pull/4711
    - https://github.com/rhinstaller/anaconda/pull/5081

Respect preferred disk label type provided by blivet (#2092091, #2209760)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In Fedora 37, anaconda was changed to always format disks with GPT
disk labels, so long as blivet reported that the platform supports
them at all (even if blivet indicated that MBR labels should be
preferred). This was intended to implement a plan to prefer GPT
disk labels on x86_64 BIOS installs, but in fact resulted in GPT
disk labels also being used in other cases. Now, we go back to
respecting the preferred disk label type indicated by blivet, by
default (a corresponding change has been made to blivet to make it
prefer GPT labels on x86_64 BIOS systems). The inst.disklabel
option can still be used to force a preference for gpt or mbr if
desired.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2092091
    - https://bugzilla.redhat.com/show_bug.cgi?id=2209760

Install an image using systemd-boot rather than grub (#2135531)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With this release, systemd-boot can be selected as an alternative boot
loader for testing and development purposes.

This can be done with ``inst.sdboot`` from the grub/kernel command
line or with ``--sdboot`` in a kickstart file as part of the
bootloader command.  The resulting machine should be free of grub,
shim, and grubby packages, with all the boot files on the EFI
System Partition (ESP). This may mean that it is wise to dedicate
the space previously allocated for ``/boot`` to the ESP in order to
assure that future kernel upgrades will have sufficient space.

For more information, refer to the anaconda and systemd-boot documentation.

See also:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2135531
    - https://github.com/rhinstaller/anaconda/pull/4368


Fedora 38
#########

Changes in the graphical interface
----------------------------------

Modernized welcome screen on Live CD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The welcome screen on Live CD has been changed to follow the current design patterns,
as well as fit better into the surrounding GTK4-based interface.
See the pull request `#4616 <https://github.com/rhinstaller/anaconda/pull/4616>`__ for more information.

Improved configuration of additional repositories in GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration of additional repositories in the graphical user interface has been improved.
The protocol selection is now replaced with a drop-down menu of source actions.
The screen also shows only configuration options relevant to the selected source action.
See the pull request `#4498 <https://github.com/rhinstaller/anaconda/pull/4498>`__ for more details.

Installation source errors are visible again
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, errors related to contents of the Installation Source screen did not cause the
error message bar to appear at the bottom of the screen. As a consequence, users could not review
the error messages and immediately correct the errors on the screen. The error message bar now
appears correctly when errors occur. As a result, users can immediately notice errors in the
Installation Source screen and correct them.
See the pull request `#4501 <https://github.com/rhinstaller/anaconda/pull/4501>`__.

Japanese translation fits the whole screen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, using Anaconda in Japanese caused the main screen elements to use larger font than in
other languages. As a consequence, the user settings were hidden outside the visible screen area
and required scrolling. The sizing has been corrected, and Japanese users can now see the user
settings icon and description even on the smallest supported screen sizes again.
See the pull request `#4325 <https://github.com/rhinstaller/anaconda/pull/4325>`__.

Architecture and hardware support changes
-----------------------------------------

Do not pass the `rd.znet` boot argument on to the installed system unconditionally
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With this change, the `rd.znet` boot argument is no longer passed on to the installed
system unconditionally on IBM Z systems and the network device is configured and
activated after switchroot by udev/NetworkManager. When networking is needed early in
initramfs (like in a case of the root file system on iSCSI), `rd.znet` is automatically
added to the kernel command line of the installed via a different mechanism.
See the pull request `#4303 <https://github.com/rhinstaller/anaconda/pull/4303>`__.

The dmraid and nodmraid boot options are removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``inst.dmraid`` and ``inst.nodmraid`` boot options have been removed. These options no longer
controlled any functionality, after Anaconda started using ``mdadm`` instead of ``dmraid``.
See the pull request `#4517 <https://github.com/rhinstaller/anaconda/pull/4517>`__ and the related
`Fedora Change <https://fedoraproject.org/wiki/Changes/UseMdadmForBIOSRAIDInAnaconda>`__.

Biosboot partition verification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The biosboot partition is now verified on all installation target disks.
This improves support for booting from an array.
See the pull request `#4277 <https://github.com/rhinstaller/anaconda/pull/4277>`__.

Multiple bootloader devices on the Manual Partitioning screen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With this change, the graphical interface displays correctly all bootloader devices on the
Manual Partitioning screen.
See the pull request `#4271 <https://github.com/rhinstaller/anaconda/pull/4271>`__.

Payload changes
-----------------

Add support for OSTree native containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fedora is adding a new enhanced container support for the (rpm-)ostree stack to
natively support OCI/Docker containers as a transport and delivery mechanism
for operating system content. Anaconda now supports these containers by
a new kickstart command `ostreecontainer`.
See the pull request `#4617 <https://github.com/rhinstaller/anaconda/pull/4617>`__,
`Fedora Change <https://fedoraproject.org/wiki/Changes/OstreeNativeContainerStable>`__
and `Pykickstart <https://pykickstart.readthedocs.io/en/latest/kickstart-docs.html#ostreecontainer>`__.

rpm-ostree now validates checksums for local repositories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Previously, rpm-ostree installations verified checksums only for installations from a remote
repository, while installations from local repositories did not verify the checksums.
As a consequence, rpm-ostree installations from local repositories could install corrupted data
without any indication. This behavior is now unified, and Anaconda verifies checksums for all
rpm-ostree repositories. As a result, all rpm-ostree installations are now protected against
installing corrupted data.
See the pull request `#4357 <https://github.com/rhinstaller/anaconda/pull/4357>`__ for more information.

Kickstart support
-----------------

Creating hibernation swap from kickstart
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The new ``autopart (...) --hibernation`` kickstart option creates a swap partition with an
automatically determined size that is big enough for hibernation.
See the pull request `#4275 <https://github.com/rhinstaller/anaconda/pull/4275>`__.

General changes
---------------

Faster core dumps
^^^^^^^^^^^^^^^^^

Previously, Anaconda used a custom setup for handling tracebacks and saving core dumps. This is
now realized by using the ``faulthandler`` Python module and the ``systemd-coredump`` service.
As a result, the same debugging data is still available, while the installation environment
becomes responsive significantly sooner after tracebacks. As a side effect, the logs from Anaconda
and the installation environment now contain different error messages.
See the pull request `#4350 <https://github.com/rhinstaller/anaconda/pull/4350>`__ for more information.

The Web UI of Anaconda is now packaged in Fedora
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda team is working for some time on the new Web UI frontend for the installer and to make
this in development Web UI more accessible to people we decided to add this as a new package to
Fedora repositories. To be able to consume this Web UI, you need to build ISO with the Web UI
package and add kernel boot arguments `inst.webui`. This package is not included in the existing
Fedora images by default.
See the pull request `#4269 <https://github.com/rhinstaller/anaconda/pull/4269>`__.

Fedora 37
#########

General changes
---------------

GPT is the default disk label type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fedora Linux systems installed on legacy x86 BIOS systems will get GPT partitioning by default
instead of legacy MBR partitioning. This should be a new default for all products. See the
`Fedora Change <https://fedoraproject.org/wiki/Changes/GPTforBIOSbyDefault>`__ for more info.

Read-only /sysroot on RPM OSTree systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The RPM OSTree installations set the ``/sysroot`` mount point as read-only instead of read-write
to make the newly installed systems more robust. Users and administrators are not expected to
directly interact with the content available there and should use the available interfaces to
manage their system. See the `pull request <https://github.com/rhinstaller/anaconda/pull/4240>`__
and the `Fedora Change <https://fedoraproject.org/wiki/Changes/Silverblue_Kinoite_readonly_sysroot>`__.

Anaconda doesn't copy /etc/resolv.conf to systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda does not copy the ``/etc/resolv.conf`` file from the installation environment to
the installed system anymore. Creating the file is a business of ``systemd-resolved`` or
the Network Manager. Anaconda is not going to interfere into this process anymore.
Currently the file is created by ``systemd-resolved`` package during the installation.
See the pull requests `#3814 <https://github.com/rhinstaller/anaconda/pull/3814>`__ and
`#3818 <https://github.com/rhinstaller/anaconda/pull/3818>`__.

Correct SELinux contexts on existing home directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, the installer set incorrect SELinux contexts on home directory contents when
reusing home directory from previous installation. The contexts are now set correctly.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/3993>`__.

Enabled hibernation on arm64 with swap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, the installer enabled resume from hibernation by adding kernel command line option
``resume=swap_device`` only on the x86 architecture family. With this change, the same is done
also for the arm64 architecture. As a result, devices of the arm64 architecture are now able to
correctly resume from hibernation.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/4221>`__.

Changed default swap size for large-memory systems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default swap size on systems with 64 GiB or more RAM is 32 GiB now. Previously, it was 4 GiB.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/4049>`__.

Removed some scripts provided by Anaconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following undocumented installed scripts were removed from `anaconda` packages:

- ``/usr/bin/analog``
- ``/usr/bin/restart-anaconda``

The following unused development scripts were removed from the Anaconda repository:

- ``run_boss_locally.py``
- ``anaconda-read-journal``
- ``list-screens``
- ``make-sphinx-docs``

See the pull requests `#3839 <https://github.com/rhinstaller/anaconda/pull/3839>`__ and
`#3838 <https://github.com/rhinstaller/anaconda/pull/3838>`__.

Changes in the graphical interface
----------------------------------

The media verification dialog is improved
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously, the media verification dialog indicated a good or bad media check result using the
same sentence, differing only in presence of a single "not". Additionally, the dialog did not
visually change much upon completion of the check. Consequently, it was not easy to interpret
the result of the media check, or even see if it was finished.

The dialog now uses a large icon to signal whether the media is good or not, and while the
check is running, this icon is absent. As a result, it is now possible to easily tell the state
of the media check. See the `pull request <https://github.com/rhinstaller/anaconda/pull/4230>`__
and the `screenshot <https://user-images.githubusercontent.com/15903878/176200267-789a86fe-e874-4b14-aa20-878e63381dca.png>`__.

Improved calculation of the space estimation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

During automatic partitioning the disk spoke estimates the space required for the installation
and if there isn't enough free space it display a warning dialog suggesting more space should
be reclaimed. This estimate included the recommended swap size even when swap wasn't configured
to be created. See the bug `2068290 <https://bugzilla.redhat.com/show_bug.cgi?id=2068290>`__.

The zFCP dialog supports NPIV-enabled devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The "Add zFCP" dialog supports NPIV-enabled zFCP devices. NPIV-enabled devices are activated just
by using the device ID. The kernel module will detect the WWPNs and LUNs and bring all the devices
up automatically. This means the user doesn't have to provide the WWPN and LUN IDs.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/4188>`__.

The timezone map doesn't show borders
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda is not showing timezone borders in the Time & Date spoke. The map is white now.
See the bug `2103657 <https://bugzilla.redhat.com/show_bug.cgi?id=2103657>`__

Changes in the kickstart support
--------------------------------

Prompt for a missing passphrase in GUI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the kickstart file defines a partitioning that requires a passphrase, the graphical user
interface shows a dialog that allows users to provide the missing passphrase. The installation
automatically continues after the passphrase is provided. It works the same way in the text user
interface. See the `pull request <https://github.com/rhinstaller/anaconda/pull/4164>`__.

``rootpw --allow-ssh`` is supported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the ``--allow-ssh`` option of ``rootpw`` kickstart command to allow remote logins of the
root user via SSH using only the password. This is disabled by default for the security reasons,
so be aware of risks. See the `pull request <https://github.com/rhinstaller/anaconda/pull/4154>`__
and the `Fedora Change <https://fedoraproject.org/wiki/Changes/DisableRootPasswordLoginInSshd>`__
for the default behaviour.

``zfcp --devnum=`` is supported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``zfcp`` kickstart command supports NPIV-enabled zFCP devices. NPIV-enabled devices are
activated just by using the device ID. The kernel module will detect the WWPNs and LUNs and
bring all the devices up automatically. This means the user doesn't have to provide the WWPN
and LUN IDs::

    zfcp --devnum=<device_number>

See the `pull request <https://github.com/pykickstart/pykickstart/pull/410>`__ for more info.

Changes in Anaconda options
---------------------------

``inst.gpt`` is deprecated
^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the ``inst.disklabel`` boot option to specify a preferred disk label type. Specify ``gpt``
to prefer creation of GPT disk labels. Specify ``mbr`` to prefer creation of MBR disk labels if
supported. The ``inst.gpt`` boot option is deprecated and will be removed in future releases.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/4232>`__.

Changes in Anaconda configuration files
---------------------------------------

The ``gpt`` option is replaced
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default value of the preferred disk label type is specified by the ``disk_label_type``
option in the Anaconda configuration files. The ``gpt`` configuration option is no longer
supported. See the `pull request <https://github.com/rhinstaller/anaconda/pull/4232>`__.

The ``decorated_window`` option is removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``decorated_windows`` option is removed from Anaconda's configuration files.
It was never requested and we have no evidence that it was used.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/3933>`__.

The ``enable_ignore_broken_packages`` option is removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``enable_ignore_broken_packages`` option in Anaconda's configuration files is removed.
The pykickstart decides whether the ``%packages --ignorebroken`` feature is supported or not.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/3897>`__.

The ``blivet_gui_supported`` option is removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for Blivet-GUI will be disabled automatically if it is not installed.
Use the ``hidden_spokes`` option of the ``User Interface`` section to disable it explicitly.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/3925>`__.

The ``can_detect_unsupported_hardware`` and ``can_detect_support_removed`` options were removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for detection of unsupported hardware is no longer available.
See the `pull request <https://github.com/rhinstaller/anaconda/pull/3842>`__ for more info.

Fedora 36
#########

General changes
---------------

The help support is unified
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The help support on RHEL and Fedora uses new mapping files with a unified format.
The mappings files are located in the root of the help directory.
For example for RHEL, they are expected to be at::

    /usr/share/anaconda/help/rhel/anaconda-gui.json
    /usr/share/anaconda/help/rhel/anaconda-tui.json

The mapping files contain data about the available help content.
The UI screens are identified by a unique screen id returned by
the ``get_screen_id`` method, for example ``installation-summary``.
The help content is defined by a relative path to a help file and
(optionally) a name of an anchor in the help file.

For example::

    {
      "_comment_": [
        "This is a comment",
        "with multiple lines."
      ],
      "_default_": {
        "file": "default-help.xml",
        "anchor": "",
      },
      "installation-summary": {
        "file": "anaconda-help.xml",
        "anchor": "",
      },
      "user-configuration": {
        "file": "anaconda-help.xml",
        "anchor": "creating-a-user-account"
      }
    }

The ``default_help_pages`` configuration option is removed. The ``helpFile`` attribute is removed
from the UI classes. See the `pull request`_ for more info.

.. _pull request:
  https://github.com/rhinstaller/anaconda/pull/3575

Changes in the graphical interface
----------------------------------

Users are administrators by default
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In the User spoke, the "Make this user administrator" checkbox is now checked by default. This
improves installation experience for users who do not know and need to rely on the default values
to guide them. See the `Users are admins by default`_ change.

.. _Users are admins by default:
   https://fedoraproject.org/wiki/Changes/Users_are_admins_by_default_in_Anaconda

Keyboard configuration is disabled on Live media with Wayland
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The keyboard switching in the Anaconda installer on the Live media did not behave as expected
on Wayland based environments (`#2016613`_). When users changed the keyboard layout configuration
that configuration was reflected in the Live environment. However, if users pressed modifier keys
(CTRL or SHIFT) the keyboard specified by the Anaconda installer was changed back for the Live
environment. That is the result of how the Wayland protocol handles keyboard layout.

To avoid this unexpected behavior Anaconda will no longer control keyboard layout configuration
of the Live systems on Wayland Live environment. The keyboard configuration set by Anaconda on
the Live environment will be reflected only to the installed system. This means that users have
to pay attention that their passwords are written by the correct layout in the installer running
inside the Live environment to be able to use the password in the system after installation.

.. _#2016613:
  https://bugzilla.redhat.com/show_bug.cgi?id=2016613

Changes in the kickstart support
--------------------------------

The `%anaconda` section is removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for the deprecated `%anaconda` section is removed.
Use `Anaconda configuration files`_ instead.

.. _Anaconda configuration files:
  https://anaconda-installer.readthedocs.io/en/latest/configuration-files.html

`ANA_INSTALL_PATH` is deprecated
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ANA_INSTALL_PATH` environment variable is deprecated. The support for this variable will be
removed in future releases. Use the `/mnt/sysroot` path in your kickstart scripts instead.
See the `Installation mount points`_ documentation.

.. _Installation mount points:
  https://anaconda-installer.readthedocs.io/en/latest/mount-points.html


Changes in Anaconda options
---------------------------

`inst.nompath` is deprecated
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `inst.nompath` boot option is deprecated. It has not been doing anything useful for some
time already.


Changes in Anaconda configuration files
---------------------------------------

Saving Anaconda's data to target system
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda configuration file format now includes additional options to control
what is saved to the target system.

The options are::

    # Should we copy input kickstart to target system?
    can_copy_input_kickstart = True

    # Should we save kickstart equivalent to installation settings to the new system?
    can_save_output_kickstart = True

    # Should we save logs from the installation to the new system?
    can_save_installation_logs = True

The default values above cause no change in behavior, the new options are
only another way to configure the behavior.

Fedora 35
#########

General changes
---------------

Limited support for braille devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Server image (boot.iso) now contains the `brltty` accessibility software.
This means that some braille output devices can be automatically detected and used.
This feature works only in text mode, started with the `inst.text` boot option.
See `the bug <https://bugzilla.redhat.com/show_bug.cgi?id=1584679>`_.

Visible warnings in initrd
^^^^^^^^^^^^^^^^^^^^^^^^^^

Installation shows critical warnings raised in Dracut/initrd again when Anaconda is
starting or when Dracut starts to timeout. This should help users to resolve installation
issues by avoiding that the important message was scrolled out too fast.
See `the bug <https://bugzilla.redhat.com/show_bug.cgi?id=1983098>`_.

Changes in the graphical interface
----------------------------------

New look of the NTP server dialog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The NTP server dialog has been redesigned. The new look uses more traditional approach to
management of lists (such as in `hexchat`). See `the pull request <https://github.com/rhinstaller/anaconda/pull/3538>`_.

- The set of controls to add a new server is no longer present. Instead, a "blank" new server
  is added by clicking an "add" button. The details can be filled in by editing the server
  in the list, as was already possible.
- The method to remove a server is now more intuitive. Users can simply click the "remove"
  button and the server is instantly removed from the list. Previously, users had to uncheck
  the "Use" checkbox for the server in the list and confirm the dialog.

New look of the root configuration screen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The root configuration screen has been redesigned and is no longer ambiguous. All root account
options are visible only if root account is enabled. The new layout also contains text to let
users understand their choices. See `the pull request <https://github.com/rhinstaller/anaconda/pull/3511>`_.

Changes in the text interface
-----------------------------

The packaging log in ``tmux`` tabs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Add a new tab to the ``tmux`` session starting the Anaconda installer. This new tab will follows
the ``/tmp/packaging.log`` log file. This change should make it easier for users to spot software
installation errors. See `the pull request <https://github.com/rhinstaller/anaconda/pull/3472>`_.

Changes in Anaconda configuration files
---------------------------------------

Replacement of product configuration files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for the product configuration files was removed and replaced with profiles.
See `the Fedora change <https://fedoraproject.org/wiki/Changes/Replace_Anaconda_product_configuration_files_with_profiles>`_
and `the documentation <https://anaconda-installer.readthedocs.io/en/latest/configuration-files.html#profile-configuration-files>`_.

Each profile can be identified by a unique id and it can define additional options for
the automated profile detection. The profile will be chosen based on the ``inst.profile``
boot option, or based on the ``ID`` and ``VARIANT_ID`` options of the os-release files.
The profile configuration files are located in the ``/etc/anaconda/profile.d/`` directory.

The ``inst.product`` and ``inst.variant`` boot options are deprecated.

Options for Anaconda DBus module activation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We have introduced new configuration options that affect the detection and activation of
the Anaconda DBus modules. Use the ``activatable_modules`` option to specify Anaconda DBus
modules that can be activated. Use the ``forbidden_modules`` option to specify modules that
are not allowed to run. Use the ``optional_modules`` to specify modules that can fail to run
without aborting the installation.

The DBus modules can be specified by a DBus name or by a prefix of the name that ends with
an asterisk. For example::

    org.fedoraproject.Anaconda.Modules.Timezone
    org.fedoraproject.Anaconda.Addons.*

The ``addons_enabled`` and ``kickstart_modules`` options are deprecated and will be removed
in the future.

See `the pull request <https://github.com/rhinstaller/anaconda/pull/3464>`_.
