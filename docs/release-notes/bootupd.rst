:Type: OSTree
:Summary: Preliminary support for bootable ostree containers

:Description:
    Anaconda can now correctly detect and use the bootupd bootloader used in
    bootable ostree containers. When the installed container includes the ``bootupctl`` tool, it
    is used instead of installing the ``grub2`` bootloader by Anaconda.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/5342
