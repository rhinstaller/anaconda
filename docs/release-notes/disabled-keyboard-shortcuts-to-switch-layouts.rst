:Type: GUI
:Summary: Disable keyboard shortcuts to switch keyboard layouts (#2307282)

:Description:
    As part of the system wide change in Fedora to migrate Anaconda to Wayland we also had
    to remove libXklavier from our codebase. That resulted in a new solution built on localed.

    The original idea was to have bidirectional communication between Anaconda and the running
    system using localed as middle layer to control keyboard layouts in the system but also
    to give a system a possibility to reflect changes from system to Anaconda. Unfortunately,
    we are facing issues that the system have a hard time reacting to keyboard layout changes.
    The selected layout is especially problematic as it is not a term to be easily defined and
    is tricky to resolve. One of the reasons is that the layout could be specific to a window
    and Anaconda is not the same process as the localed daemon.

    To simplify this issue we have decided to disable keyboard layout switching by keyboard
    shortcuts. This will allow us to change the bidirectional solution in Anaconda to one direction
    which is only::

        Anaconda > localed > system

    That should make Anaconda solution more robust and also will remove burden from the Desktop
    maintainers that they don't need to add implementation to be able to detect changes and set
    them correctly to the localed.

:Links:
    - https://fedoraproject.org/wiki/Changes/Anaconda_As_Native_Wayland_Application
    - https://bugzilla.redhat.com/show_bug.cgi?id=2307282
    - https://bugzilla.redhat.com/show_bug.cgi?id=1955025
