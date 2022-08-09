:Type: Installation
:Summary: SELinux contexts are correctly set on existing home directories

:Description:
    Previously, the installer set incorrect SELinux contexts on home directory contents when
    reusing home directory from previous installation. The contexts are now set correctly.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/3993
