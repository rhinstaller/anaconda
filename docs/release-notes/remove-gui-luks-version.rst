:Type: GUI
:Summary: Remove support for the LUKS version selection from GUI

:Description:
    All widgets for the LUKS version selection were removed from the "Manual Partitioning"
    screen of the GTK-based graphical user interface. The installer will use the ``luks2``
    version by default for all new devices and keep the LUKS version of existing ones. Use
    the kickstart support or Blivet GUI to select the LUKS version.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/5395
