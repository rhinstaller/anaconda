Common bugs and issues
======================

Below you will find the most common bugs and issues, that we encounter at Bugzilla, and their
solutions.

Bug report issues
-----------------

These issues require more information from the reporter.

Too old version of Anaconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The bug is reported against a too old version of the operating system. It it possible
    that the code has changed and the problem no longer exists.
:Solution: Are you able to reproduce the problem with Fedora XY?

Missing logs
^^^^^^^^^^^^

:Issue: There are no useful logs attached to the bug.
:Solution: Please, attach all files with installation logs, especially the file named ``syslog``.
    You can find them during the installation in ``/tmp`` or on the installed system in
    ``/var/log/anaconda/``.

DBus issues
-----------

Anaconda runs several DBus modules and communicates with them from the user interface, so you can
easily come across a DBus-related issue.

Traceback of DBusError
^^^^^^^^^^^^^^^^^^^^^^

:Issue: Anaconda fails with the ``dasbus.error.DBusError`` exception. This usually happens
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

:Issue: Anaconda fails early in stage2 with an exception "ValueError: new value non-existent
    xfs filesystem is not valid as a default fs type".
:Solution: This error occurs when ``initrd.img``, ``vmlinuz`` and the repository (or stage2) are
    not from the same media or location.
:Example: `rhbz#1169034 <https://bugzilla.redhat.com/show_bug.cgi?id=1169034>`_

Out of memory
^^^^^^^^^^^^^

:Issue: Anaconda fails in stage1 with a message "Failed writing body" or "No space left on
    device" in the dracut logs. This usually happens when installing from http or ftp source on
    a machine with insufficient memory size. See the
    `minimal requirements <https://access.redhat.com/articles/rhel-limits>`_ for RHEL.
:Solution: Increase the memory size or try installing from NFS, CD-Rom or HDD source.
:Example: `rhbz#1630763 <https://bugzilla.redhat.com/show_bug.cgi?id=1630763>`_

Changes in Live OS
^^^^^^^^^^^^^^^^^^

:Issue: The Live OS requires changes.
:Solution: Reassigning to spin-kickstarts.

Changes in boot.iso
^^^^^^^^^^^^^^^^^^^

:Issue: The ``boot.iso`` requires changes.
:Solution: Reassigning to lorax.

Icon issues
^^^^^^^^^^^

:Issue: The Anaconda icons in Live OS requires changes.
:Solution: Reassigning to fedora-logos
:Example: `rhbz#1699034 <https://bugzilla.redhat.com/show_bug.cgi?id=1699034>`_

Font issues
^^^^^^^^^^^

:Issue: In the Welcome spoke, there are replacement glyphs (rectangles) instead of
    characters in a name of a language. This usually means that that there is no font for this
    language installed in the installation environment.
:Solution: Reassigning to lorax or spin-kickstarts.
:Example: `rhbz#1530086 <https://bugzilla.redhat.com/show_bug.cgi?id=1530086>`_

Payload issues
--------------

These issues are related to the content that is installed on the target system.

Non-fatal POSTIN scriptlet failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The package installation fails with a message "Non-fatal POSTIN scriptlet failure in
    rpm package". The failing package has to fix its scriptlet, because `all scriptlets
    MUST exit with the zero exit status.
    <https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/>`_
:Solution: All RPM errors are fatal during the installation (see the bug 1565123). Reassigning.
:Example: `rhbz#1588409 <https://bugzilla.redhat.com/show_bug.cgi?id=1588409>`_

Changes in package groups and environments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The reporter wants a new package to be installed by default.
:Solution: Reassigning to comps.
:Example: `rhbz#1787018 <https://bugzilla.redhat.com/show_bug.cgi?id=1787018>`_

Corrupted ISO
^^^^^^^^^^^^^

:Issue: The package installation fails with a message "Some packages from local repository
    have incorrect checksum". This happens when the packages cannot be accessed, because they
    are located on a corrupted ISO or an unmounted device.
:Solution: The ISO might be corrupted. Please, try to download it again and verify the checksum.
:Example: `rhbz#1551311 <https://bugzilla.redhat.com/show_bug.cgi?id=1551311>`_

Issues with live payload
^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The image installed by the live OS payload requires changes.
:Solution: Anaconda doesn't create the live image. Reassigning to spin-kickstarts.

Issues with OSTree
^^^^^^^^^^^^^^^^^^

:Issue: The installation with the OSTree payload fails.
:Solution: It might be related to the OSTree payload. Reassigning to Colin Walters.

Failed to mount the install tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The payload fails to set up and raises the error "Failed to mount the install tree".
    This usually happens when Anaconda is unexpectedly terminated and started again. Some of
    the Anaconda's mount points stays mounted and that causes the crash.
:Example: `rhbz#1562239 <https://bugzilla.redhat.com/show_bug.cgi?id=1562239>`_

System upgrades
^^^^^^^^^^^^^^^

:Issue: The system was upgraded, not installed.
:Solution: Anaconda is not doing system upgrades. That is done by dnf-system-upgrade.
    Reassigning to dnf.

Storage issues
--------------

These issues are related to hardware, partitioning and storage configuration.

Bug in blivet
^^^^^^^^^^^^^

:Issue: The exception starts in ``blivet`` or ``libblockdev``.
:Solution: It seems to be an issue in the storage configuration library. Reassigning to blivet.
:Example: `rhbz#1827254 <https://bugzilla.redhat.com/show_bug.cgi?id=1827254>`_

Bug in blivet-gui
^^^^^^^^^^^^^^^^^

:Issue: The exception starts in ``blivet-gui`` or there is a problem with partitioning and
    the reporter used Blivet-GUI as the partitioning method.
:Solution: It seems to be an issue in blivet-gui. Reassigning.
:Example: `rhbz#1833775 <https://bugzilla.redhat.com/show_bug.cgi?id=1833775>`_

Failing hardware
^^^^^^^^^^^^^^^^

:Issue: The logs (journal or syslog) are full of kernel messages about I/O errors. For
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

:Issue: The storage configuration fails with an error message mentioning "inconsistent sector
    size".
:Solution: LVM is now demanding that all disks have consistent sector size, otherwise they can't
    be used together. Please adjust your disk selection to use only disks with the consistent
    sector size.
:Example: `rhbz#1754683 <https://bugzilla.redhat.com/show_bug.cgi?id=1754683>`_

Unlocked LUKS
^^^^^^^^^^^^^

:Issue: The storage configuration fails with a message "luks device not configured".
:Solution: Anaconda doesn't support LUKS devices that are unlocked outside the installer. The
    device has to be unlocked in Anaconda.
:Example: `rhbz#1624856 <https://bugzilla.redhat.com/show_bug.cgi?id=1624856>`_

Undetected partitions
^^^^^^^^^^^^^^^^^^^^^

:Issue: When the custom partitioning spoke is entered, it raises an exception with a message:
    "cannot initialize a disk that has partitions". Anaconda tries to initialize disks that are
    supposed to be empty, but there are partitions that were not discovered by kernel after boot.
:Solution: Duplicate of the bug 1825067.
:Example: `rhbz#1828188 <https://bugzilla.redhat.com/show_bug.cgi?id=1828188>`_

Too little memory for LUKS setup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: Anaconda crashes with an exception: ``No such interface “org.freedesktop.DBus.Properties” on object at path /org/fedoraproject/Anaconda/Modules/Storage/Task/`` .
:Solution: The installation environment does not have enough memory to run LUKS setup, and its
    crash resets the Storage module. In logs, the following lines can be found:

    - ``WARNING:blivet:Less than (...) MiB RAM is currently free, LUKS2 format may fail.``
    - ``ui.gui.spokes.storage: Partitioning has been applied: ValidationReport(error_messages=[], warning_messages=['The available memory is less than 128 MiB which can be too small for LUKS2 format. It may fail.'])``
    - ``Activating service name='org.fedoraproject.Anaconda.Modules.Storage'`` (present more than once)

    Note that the user must have ignored a warning in the GUI.

:Workaround:
  There are several possible workarounds:

  - Use more memory for the machine,
  - use ``--pbkdf*`` options in kickstart file,
  - change LUKS version to ``LUKS1``,
  - disable encryption.

:Example: `rhbz#1902464 <https://bugzilla.redhat.com/show_bug.cgi?id=1902464>`_

Using ignoredisk on previous LVM installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: When starting installation with automatic partitioning and using ``ignoredisk``
     kickstart command, it raises an exception with a message: "Selected disks vda, vdb contain volume
     group 'vg0' that also uses further unselected disks. You must select or de-select all these
     disks as a set."
:Solution: Anaconda won't touch disks in ``ignoredisk`` kickstart command, however, other disks
     have part of a Volume Group which is also on disk ignored by the  ``ignoredisk`` command.
     To resolve this issue the ignored disks have to be erased manually or by ``%pre``
     section similar to::

      vgchange -an
      wipefs -a /dev/vda1 /dev/vda

:Example: `rhbz#1688478 <https://bugzilla.redhat.com/show_bug.cgi?id=1688478>`_

Bootloader issues
-----------------

There issues are related to bootloader issues.

Bug in bootloader
^^^^^^^^^^^^^^^^^

:Issue: The exception is raised during a bootloader installation with a message that usually
    says "failed to write bootloader" or "boot loader install failed". Look into ``program.log``
    or ``storage.log`` for more information.
:Solution: Could the bootloader team have a look at this bug, please?

Disable ``rhgb quiet``
^^^^^^^^^^^^^^^^^^^^^^

:Issue: The reporter doesn't want the default boot options ``rhgb quiet`` to be used.
:Solution: The installer adds the boot options ``rhgb quiet`` only if ``plymouth`` is installed.
    In a kickstart file, you can disable these options with the following snippet::

        %packages
        -plymouth
        %end

Invalid environment block
^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The bootloader installation fails with an exception "failed to write boot loader
    configuration". You can find the following message in the logs::

        /usr/bin/grub2-editenv: error: invalid environment block

:Solution: Duplicate of the bug 1814690.
:Example: `rhbz#1823104 <https://bugzilla.redhat.com/show_bug.cgi?id=1823104>`_

User interface issues
---------------------

These issues are related to the text and graphical user interfaces of the installation program.

Allocating size to pyanaconda+ui+gui+MainWindow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: Anaconda shows a Gtk warning "Allocating size to pyanaconda+ui+gui+MainWindow
    without calling gtk_widget_get_preferred_width/height(). How does the code know the size to
    allocate?"
:Solution: This is an issue in the GTK library: See: `<https://gitlab.gnome.org/GNOME/gtk/issues/658>`_
:Example: `rhbz#1619811 <https://bugzilla.redhat.com/show_bug.cgi?id=1619811>`_

Bug in Gtk
^^^^^^^^^^

:Issue: When Anaconda is started in the graphical mode, some of the Gtk widgets look weird.
:Solution: Reassigning to gtk3.

Weirdly displayed GUI
^^^^^^^^^^^^^^^^^^^^^

:Issue: When Anaconda is started in the graphical mode, the whole screen looks weird.
:Solution: It looks like an Xorg or kernel issue. Reassigning to xorg-x11 for further triaging.

Rotated screen
^^^^^^^^^^^^^^

:Issue: The screen is rotated.
:Solution: It seems to be a problem with drivers. Reassigning to kernel.
:Contact: kernel or iio-sensor-proxy

Localization issues
-------------------

These issues are related to the localization support in Anaconda.

Changes in localization data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: Languages, locales, keyboard layouts or territories are not correct.
:Solution: This content is provided by langtable. Reassigning.
:Example: `rhbz#1698984 <https://bugzilla.redhat.com/show_bug.cgi?id=1698984>`_

Kickstart issues
----------------

These issues are related to automated installations that use kickstart files.

Automatic installation in Live OS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The reporter would like to run a kickstart installation in Live OS.
:Solution: Kickstart installations in Live OS are not supported. Please, run the installation with
    ``boot.iso``.
:Example: `rhbz#1027160 <https://bugzilla.redhat.com/show_bug.cgi?id=1027160>`_

Invalid partitioning in the output kickstart file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The kickstart file generated by Anaconda at the end of the installation defines an
    invalid partitioning.
:Solution: This part of the kickstart file is generated by the storage configuration library.
    Reassigning to blivet.
:Example: `rhbz#1851230 <https://bugzilla.redhat.com/show_bug.cgi?id=1851230>`_

The `ignoredisk --only-use` command hides installation sources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The installer fails to find an installation media on the USB drive if the `ignoredisk
    --only-use=` command is specified in a kickstart file.
:Workaround: You can use the `harddrive` command instead of the `cdrom` command. For example:

        harddrive --partition=sda --dir=/

    where `sda` is the name of the USB device, or use `LABEL`:

        harddrive --partition=LABEL=CentOS-8-3-2011-x86_64-dvd --dir=/

:Example: `rhbz#1945779 <https://bugzilla.redhat.com/show_bug.cgi?id=1945779>`_

Missing options of the `repo` command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: The `repo` kickstart command doesn't support the requested configuration options.
:Workaround: We get a lot of feature requests for the `repo` command, but we don't really want
    to support every repo configuration option. Please, use a repo file to configure the repo.

    For example::

        # Enable the custom repo.
        repo --name "my-custom-repo"

        %pre
        # Generate the custom repo file.
        cat >> /etc/anaconda.repos.d/custom.repo << EOF

        [my-custom-repo]
        name=My Custom Repository
        baseurl=http://my/custom/repo/url/
        priority=10
        module_hotfixes=1

        EOF
        %end

Enabling root password SSH login via password.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Issue: There is no kickstart command or option to enable password based root login via SSH.

:Solution: It's really not good practice to enable password based SSH root login on a machine
    as the attacker only needs to guess a password for root and then gets full access to the machine.
    For a user account the attacker needs to guess both the username and password and might only get to
    a non-admin user, making such an attack much harder and less worthwhile.

    This was the reasoning for the OpenSSH project `disabling password logins for root back in 2015
    <http://www.openssh.com/txt/release-7.0>`_.
    Fedora patched this out temporarily but in 2019 it was decided to `drop this downstream patch and respect
    the upstream behavior <https://fedoraproject.org/wiki/Changes/DisableRootPasswordLoginInSshd>`_
    of not allowing password based root login over SSH by default.
    Anaconda accommodated this change by adding and override checkbox in the root password GUI to make the transition
    easier for users still needing SSH login via root during the transition period.

    While there is currently no set deadline for removing the checkbox from the GUI, it is still considered a temporary
    element helping users during the transition to future where no use cases requiring password based root login exist.
    The option will most likely be dropped in the longer term, when it is considered no longer necessary
    - of course with a proper heads-up and feedback period for the Anaconda user community.

    This is also the reason why we did not add any kickstart support for the SSH root password login override
    - dropping something from the GUI is certainly not without impact, but doing the same for a kickstart
    command or option is much harder.

    Also as already mentioned above, enabling password based root login over SSH can quite significantly compromise
    the security of a system and should be an explicit and easy to spot action performed by the user during the installation.
    Clicking a checkbox satisfies this condition in the GUI.

    A kickstart command option on the other hand could be easily missed during the common practice of reusing kickstarts
    and kickstart snippets - there are already quite a few options even just for the rootpw command and one more option copy pasted
    from a test-run kickstart could easily by missed & turn all production image installs vulnerable to remote password guessing attack.

:Workaround: If you really need to enable password based SSH root login, you can just easily use the following two line
    %post script (one line without comments)::

        %post
        # permit root login via SSH with password authetication
        echo "PermitRootLogin yes" > /etc/ssh/sshd_config.d/01-permitrootlogin.conf
        %end

    This does 100% the same as a rootpw command option would, but unlike the option is quite explicit about what it does
    and easy to spot in a kickstart file. Or even better, use the sshkey command to use a key instead of password,
    making a remote guessing attack essentially impossible.
