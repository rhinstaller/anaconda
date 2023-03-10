:Type: Kickstart Installation
:Summary: Install an image using systemd-boot rather than grub (#2135531)

:Description:
    With this release, systemd-boot can be selected as an alternative boot
    loader for testing and development purposes.

    This can be done with 'inst.sdboot' from the grub/kernel command
    line or with '--sdboot' in a kickstart file as part of the
    bootloader command.  The resulting machine should be free of grub,
    shim, and grubby packages, with all the boot files on the EFI
    System Partition (ESP). This may mean that it is wise to dedicate
    the space previously allocated for /boot to the ESP in order to
    assure that future kernel upgrades will have sufficient space.

    For more information, refer to the anaconda and systemd-boot documentation.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2135531
    - https://github.com/rhinstaller/anaconda/pull/4368
