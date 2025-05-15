:Type: Core / Flatpak
:Summary: Initial support for Flatpak preinstall

:Description:
    This is initial support for Flatpak preinstall feature. This feature allows marking flatpaks
    for the installation from the target system payload. The benefit of this functionality is that
    it is attached to the original payload (DNF packages, bootc container images…).

    The current implementation is not used in Fedora but the plan is to use this in future
    Fedora Atomic desktops and maybe even Workstation to deliver some of the applications
    as Flatpaks seemingly.

    To mark Flatpaks for installation in the current implementation you need to have a package
    based installation and install a package with Provides similar to
    ``flatpak-preinstall(app/org.mozilla.firefox//stable)`` and correctly installing
    ``/etc/flatpak/preinstall.d`` configuration. With such a package installed to
    the system Anaconda will also install the ``org.mozilla.firefox`` Flatpak.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/6056
    - https://github.com/flatpak/flatpak/issues/5579

