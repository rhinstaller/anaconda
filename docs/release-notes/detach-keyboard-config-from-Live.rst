:Type: GUI
:Summary: Split keyboard configuration between Live media and system to be installed (#2016613)

:Description:
    The keyboard switching in the Anaconda installer on the Live media did not behave as expected
    on Wayland based environments. When users changed the keyboard layout configuration that
    configuration was reflected in the Live environment. However, if users pressed modifier keys
    (CTRL or SHIFT) the keyboard specified by the Anaconda installer was changed back for the Live
    environment. That is the result of how the Wayland protocol handles keyboard layout.

    To avoid this unexpected behavior Anaconda will no longer control keyboard layout
    configuration of the Live systems on Wayland Live environment. The keyboard configuration set
    by Anaconda on the Live environment will be reflected only to the installed system.

    BEWARE::

      This means that users have to pay attention that their passwords are written by the correct
      layout in the installer running inside the Live environment to be able to use the password in
      the system after installation.
:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2016613
    - https://github.com/rhinstaller/anaconda/pull/3912
