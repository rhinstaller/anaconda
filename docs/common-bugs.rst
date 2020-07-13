Common bugs and issues
======================

Below you will find the most common bugs and issues, that we encounter at Bugzilla, and their
solutions.

Bug report issues
-----------------

These issues require more information from the reporter.

Too old version of Anaconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The bug is reported against a too old version of the operating system. It it possible
    that the code has changed and the problem no longer exists.
:Solution: Are you able to reproduce the problem with Fedora XY?

Missing logs
^^^^^^^^^^^^

:Detection: There are no useful logs attached to the bug.
:Solution: Please, attach all files with installation logs, especially the file named ``syslog``.
    You can find them during the installation in ``/tmp`` or on the installed system in
    ``/var/log/anaconda/``.

DBus issues
-----------

Anaconda runs several DBus modules and communicates with them from the user interface, so you can
easily come across a DBus-related issue.

Traceback of DBusError
^^^^^^^^^^^^^^^^^^^^^^

:Detection: Anaconda fails with the ``dasbus.error.DBusError`` exception. This usually happens
    when a DBus module raises an unexpected exception. Anaconda shows a traceback only for the
    DBus call, so it is necessary to look up a traceback of the DBus module to have complete
    information about the bug.
:Solution: You can find the original exception in the logs (usually in ``syslog`` or in the output
    of ``journalctl``).
:Example: `rhbz#1828614 <https://bugzilla.redhat.com/show_bug.cgi?id=1828614>`_

Installation environment issues
-------------------------------

You can find here issues related to the installation environment. Anaconda usually runs in the
stage2 environment provided by ``boot.iso``, in Live OS, in a mock environment or locally.

Mismatched stage2
^^^^^^^^^^^^^^^^^

:Detection: Anaconda fails early in stage2 with an exception "ValueError: new value non-existent
    xfs filesystem is not valid as a default fs type".
:Solution: This error occurs when ``initrd.img``, ``vmlinuz`` and the repository (or stage2) are
    not from the same media or location.
:Example: `rhbz#1169034 <https://bugzilla.redhat.com/show_bug.cgi?id=1169034>`_

Out of memory
^^^^^^^^^^^^^

:Detection: Anaconda fails in stage1 with a message "Failed writing body" or "No space left on
    device" in the dracut logs. This usually happens when installing from http or ftp source on
    a machine with insufficient memory size. See the
    `minimal requirements <https://access.redhat.com/articles/rhel-limits>`_ for RHEL.
:Solution: Increase the memory size or try installing from NFS, CD-Rom or HDD source.
:Example: `rhbz#1630763 <https://bugzilla.redhat.com/show_bug.cgi?id=1630763>`_

Changes in Live OS
^^^^^^^^^^^^^^^^^^

:Detection: The Live OS requires changes.
:Solution: Reassigning to spin-kickstarts.

Changes in boot.iso
^^^^^^^^^^^^^^^^^^^

:Detection: The ``boot.iso`` requires changes.
:Solution: Reassigning to lorax.

Icon issues
^^^^^^^^^^^

:Detection: The Anaconda icons in Live OS requires changes.
:Solution: Reassigning to fedora-logos
:Example: `rhbz#1699034 <https://bugzilla.redhat.com/show_bug.cgi?id=1699034>`_

Font issues
^^^^^^^^^^^

:Detection: In the Welcome spoke, there are replacement glyphs (rectangles) instead of
    characters in a name of a language. This usually means that that there is no font for this
    language installed in the installation environment.
:Solution: Reassigning to lorax or spin-kickstarts.
:Example: `rhbz#1530086 <https://bugzilla.redhat.com/show_bug.cgi?id=1530086>`_

Payload issues
--------------

These issues are related to the content that is installed on the target system.

Non-fatal POSTIN scriptlet failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The package installation fails with a message "Non-fatal POSTIN scriptlet failure in
    rpm package". The failing package has to fix its scriptlet, because `all scriptlets
    MUST exit with the zero exit status.
    <https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/>`_
:Solution: All RPM errors are fatal during the installation (see the bug 1565123). Reassigning.
:Example: `rhbz#1588409 <https://bugzilla.redhat.com/show_bug.cgi?id=1588409>`_

Changes in package groups and environments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The reporter wants a new package to be installed by default.
:Solution: Reassigning to comps.
:Example: `rhbz#1787018 <https://bugzilla.redhat.com/show_bug.cgi?id=1787018>`_

Corrupted ISO
^^^^^^^^^^^^^

:Detection: The package installation fails with a message "Some packages from local repository
    have incorrect checksum". This happens when the packages cannot be accessed, because they
    are located on a corrupted ISO or an unmounted device.
:Solution: The ISO might be corrupted. Please, try to download it again and verify the checksum.
:Example: `rhbz#1551311 <https://bugzilla.redhat.com/show_bug.cgi?id=1551311>`_

Issues with live payload
^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The image installed by the live OS payload requires changes.
:Solution: Anaconda doesn't create the live image. Reassigning to spin-kickstarts.

Issues with OSTree
^^^^^^^^^^^^^^^^^^

:Detection: The installation with the OSTree payload fails.
:Solution: It might be related to the OSTree payload. Reassigning to Colin Walters.

Failed to mount the install tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The payload fails to set up and raises the error "Failed to mount the install tree".
    This usually happens when Anaconda is unexpectedly terminated and started again. Some of
    the Anaconda's mount points stays mounted and that causes the crash.
:Example: `rhbz#1562239 <https://bugzilla.redhat.com/show_bug.cgi?id=1562239>`_

System upgrades
^^^^^^^^^^^^^^^

:Detection: The system was upgraded, not installed.
:Solution: Anaconda is not doing system upgrades. That is done by dnf-system-upgrade.
    Reassigning to dnf.

Storage issues
--------------

These issues are related to hardware, partitioning and storage configuration.

Bug in blivet
^^^^^^^^^^^^^

:Detection: The exception starts in ``blivet`` or ``libblockdev``.
:Solution: It seems to be an issue in the storage configuration library. Reassigning to blivet.
:Example: `rhbz#1827254 <https://bugzilla.redhat.com/show_bug.cgi?id=1827254>`_

Bug in blivet-gui
^^^^^^^^^^^^^^^^^

:Detection: The exception starts in ``blivet-gui`` or there is a problem with partitioning and
    the reporter used Blivet-GUI as the partitioning method.
:Solution: It seems to be an issue in blivet-gui. Reassigning.
:Example: `rhbz#1833775 <https://bugzilla.redhat.com/show_bug.cgi?id=1833775>`_

Failing hardware
^^^^^^^^^^^^^^^^

:Detection: The logs (journal or syslog) are full of kernel messages about I/O errors. For
    example::

        kernel: [sdb] tag#9 FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_SENSE
        kernel: [sdb] tag#9 Sense Key : Medium Error [current]
        kernel: [sdb] tag#9 Add. Sense: Unrecovered read error - auto reallocate failed
        kernel: [sdb] tag#9 CDB: Read(10) 28 00 1d 04 10 00 00 00 08 00
        kernel: print_req_error: I/O error, dev sdb, sector 486805504

:Solution: It looks like a hardware failure. Please, check your hardware.
:Example: `rhbz#1685047 <https://bugzilla.redhat.com/show_bug.cgi?id=1685047>`_

LVM on disks with inconsistent sector size
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The storage configuration fails with an error message mentioning "inconsistent sector
    size".
:Solution: LVM is now demanding that all disks have consistent sector size, otherwise they can't
    be used together. Please adjust your disk selection to use only disks with the consistent
    sector size.
:Example: `rhbz#1754683 <https://bugzilla.redhat.com/show_bug.cgi?id=1754683>`_

Unlocked LUKS
^^^^^^^^^^^^^

:Detection: The storage configuration fails with a message "luks device not configured".
:Solution: Anaconda doesn't support LUKS devices that are unlocked outside the installer. The
    device has to be unlocked in Anaconda.
:Example: `rhbz#1624856 <https://bugzilla.redhat.com/show_bug.cgi?id=1624856>`_

Undetected partitions
^^^^^^^^^^^^^^^^^^^^^

:Detection: When the custom partitioning spoke is entered, it raises an exception with a message:
    "cannot initialize a disk that has partitions". Anaconda tries to initialize disks that are
    supposed to be empty, but there are partitions that were not discovered by kernel after boot.
:Solution: Duplicate of the bug 1825067.
:Example: `rhbz#1828188 <https://bugzilla.redhat.com/show_bug.cgi?id=1828188>`_

Bootloader issues
-----------------

There issues are related to bootloader issues.

Bug in bootloader
^^^^^^^^^^^^^^^^^

:Detection: The exception is raised during a bootloader installation with a message that usually
    says "failed to write bootloader" or "boot loader install failed". Look into ``program.log``
    or ``storage.log`` for more information.
:Solution: Could the bootloader team have a look at this bug, please?

Disable ``rhgb quiet``
^^^^^^^^^^^^^^^^^^^^^^

:Detection: The reporter doesn't want the default boot options ``rhgb quiet`` to be used.
:Solution: The installer adds the boot options ``rhgb quiet`` only if ``plymouth`` is installed.
    In a kickstart file, you can disable these options with the following snippet::

        %packages
        -plymouth
        %end

Invalid environment block
^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The bootloader installation fails with an exception "failed to write boot loader
    configuration". You can find the following message in the logs::

        /usr/bin/grub2-editenv: error: invalid environment block

:Solution: Duplicate of the bug 1814690.
:Example: `rhbz#1823104 <https://bugzilla.redhat.com/show_bug.cgi?id=1823104>`_

User interface issues
---------------------

These issues are related to the text and graphical user interfaces of the installation program.

Allocating size to pyanaconda+ui+gui+MainWindow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: Anaconda shows a Gtk warning "Allocating size to pyanaconda+ui+gui+MainWindow
    without calling gtk_widget_get_preferred_width/height(). How does the code know the size to
    allocate?"
:Solution: This is an issue in the GTK library: See: `<https://gitlab.gnome.org/GNOME/gtk/issues/658>`_
:Example: `rhbz#1619811 <https://bugzilla.redhat.com/show_bug.cgi?id=1619811>`_

Bug in Gtk
^^^^^^^^^^

:Detection: When Anaconda is started in the graphical mode, some of the Gtk widgets look weird.
:Solution: Reassigning to gtk3.

Weirdly displayed GUI
^^^^^^^^^^^^^^^^^^^^^

:Detection: When Anaconda is started in the graphical mode, the whole screen looks weird.
:Solution: It looks like an Xorg or kernel issue. Reassigning to xorg-x11 for further triaging.

Rotated screen
^^^^^^^^^^^^^^

:Detection: The screen is rotated.
:Solution: It seems to be a problem with drivers. Reassigning to kernel.
:Contact: kernel or iio-sensor-proxy

Localization issues
-------------------

These issues are related to the localization support in Anaconda.

Changes in localization data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: Languages, locales, keyboard layouts or territories are not correct.
:Solution: This content is provided by langtable. Reassigning.
:Example: `rhbz#1698984 <https://bugzilla.redhat.com/show_bug.cgi?id=1698984>`_

Kickstart issues
----------------

These issues are related to automated installations that use kickstart files.

Automatic installation in Live OS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The reporter would like to run a kickstart installation in Live OS.
:Solution: Kickstart installations in Live OS are not supported. Please, run the installation with
    ``boot.iso``.
:Example: `rhbz#1027160 <https://bugzilla.redhat.com/show_bug.cgi?id=1027160>`_

Invalid partitioning in the output kickstart file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Detection: The kickstart file generated by Anaconda at the end of the installation defines an
    invalid partitioning.
:Solution: This part of the kickstart file is generated by the storage configuration library.
    Reassigning to blivet.
:Example: `rhbz#1851230 <https://bugzilla.redhat.com/show_bug.cgi?id=1851230>`_
