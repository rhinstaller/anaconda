:Type: RPMOSTree
:Summary: RPMOSTree installations have /sysroot mount as 'ro' (#2086489)

:Description:
    Before this change the RPMOSTree installations set the /sysroot mount point as ReadWrite,
    with this change it's mounted as ReadOnly. On rpm-ostree based systems, the real root
    (the root directory of the root partition on the disk) is mounted under the /sysroot path.
    Changing something in the /sysroot could break the system after reboot.

    This change is making the newly installed OSTree based systems more robust.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2044229
    - https://github.com/rhinstaller/anaconda/pull/4240
    - https://fedoraproject.org/wiki/Changes/Silverblue_Kinoite_readonly_sysroot
