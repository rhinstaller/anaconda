:Type: Architecture support
:Summary: Do not pass the `rd.znet` boot argument on to the installed system unconditionally

:Description:
    With this change, the `rd.znet` boot argument is no longer passed on to the installed
    system unconditionally on IBM Z systems and the network device is configured and
    activated after switchroot by udev/NetworkManager. When networking is needed early in
    initramfs (like in a case of the root file system on iSCSI), `rd.znet` is automatically
    added to the kernel command line of the installed via a different mechanism.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4303
