:Type: Architecture support
:Summary: Installer enables resume on arm64 systems

:Description:
    Previously, the installer enabled resume from hibernation by adding kernel command line option
    `resume=swap_device` only on the x86 architecture family. With this change, the same is done
    also for the arm64 architecture. As a result, devices of the arm64 architecture are now able to
    correctly resume from hibernation.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4221
