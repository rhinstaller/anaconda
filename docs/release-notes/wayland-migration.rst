:Type: GUI
:Summary: Migrate Anaconda to Wayland application (#2231339)

:Description:
    This change enables Anaconda to run natively on Wayland. Previously, Anaconda operated as an
    Xorg application or relied on XWayland for support.

    By implementing this update, we can eliminate dependencies on X11 and embrace newer, more
    secure technologies.

    By this change some kernel boot options can't be used:

    - inst.usefbx
    - inst.xdriver

:Links:
    - https://fedoraproject.org/wiki/Changes/Anaconda_As_Native_Wayland_Application
    - https://github.com/rhinstaller/anaconda/pull/5829
