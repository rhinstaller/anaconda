:Type: Bootloader
:Summary: Make the EFI System Partition at least 500MiB in size

:Description:
    The minimum size of the EFI System Partition (ESP) created by Anaconda has changed from 200 MiB to 500 MiB. The maximum size, which is used in most cases, remains at 600 MiB.

    The reasons for this change include:
    - This partition is used to deploy firmware updates. These updates need free space of twice the SPI flash size, which will grow from 64 to 128 MiB in near future and make the current partition size too small.
    - The new minimum is identical with what Microsoft mandates OEMs allocate for the partition.

:Links:
    - https://fedoraproject.org/wiki/Changes/BiggerESP
    - https://github.com/rhinstaller/anaconda/pull/4711
    - https://github.com/rhinstaller/anaconda/pull/5081
