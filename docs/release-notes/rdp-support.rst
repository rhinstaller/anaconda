:Type: GUI
:Summary: Replace VNC with RDP (#2231339)

:Description:
    As part of the X11 dependencies removals, Anaconda also drops VNC. As a replacement
    RDP (Remote Desktop Protocol) is implemented.

    What has changed:
    - Adding new kernel boot arguments: ``inst.rdp``, ``inst.rdp.username``, ``inst.rdp.password``.
    - Drop existing kernel boot argument: ``inst.vnc``, ``inst.vncpassword``, ``inst.vncconnect``.
    - Drop the existing ``vnc`` kickstart command.

:Links:
    - https://fedoraproject.org/wiki/Changes/Anaconda_As_Native_Wayland_Application
    - https://github.com/rhinstaller/anaconda/pull/5829
    - https://bugzilla.redhat.com/show_bug.cgi?id=1955025
