:Type: Live Environment
:Summary: Use keyboard layout configuration from the Live system

:Description:
    Until now, users had to specify keyboard layout for the Live environment manually in Anaconda.
    With this change, live system itself is responsible for the keyboard configuration and
    Anaconda just reads the configuration from the live system for the installed system.

    The live keyboard layout is used automatically only if the user does not specify it manually.
    At this moment, only Gnome Shell environment is supported.

    This is proper fix for https://bugzilla.redhat.com/show_bug.cgi?id=2016613 which was resolved
    by a workaround in the past.
    It is also a step forward to resolve https://bugzilla.redhat.com/show_bug.cgi?id=1955025 .

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4976
    - https://bugzilla.redhat.com/show_bug.cgi?id=2016613
    - https://bugzilla.redhat.com/show_bug.cgi?id=1955025
