:Type: General
:Summary: Limit /boot on RAID1 only (#2354805)

:Description:
    Anaconda allowed all RAID supports in the past for /boot partition, however, based on
    the current RHEL documentation and validation with the bootloader team, we have decided to
    limit the support to RAID1 only. As RAID1 is the only tested and supported FS.

    This change should increase robustness of the systems installed by Anaconda.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2354805
    - https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html-single/automatically_installing_rhel/index#raid_kickstart-commands-for-handling-storage
