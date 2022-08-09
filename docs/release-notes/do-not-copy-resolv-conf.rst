:Type: Software Installation
:Summary: Do not copy installer /etc/resolv.conf to installed system

:Description:
    Anaconda does not copy /etc/resolv.conf file from installer environment to
    the installed system anymore. Creating the file is a business of
    systemd-resolved or NetworkManager. Anaconda is not going to interfere
    into this process anymore.

    Currently the file is created by systemd-resolved package during
    installation.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/3814
    - https://github.com/rhinstaller/anaconda/pull/3818
