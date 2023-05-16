:Type: Modularization
:Summary: New Runtime module

:Description:
    Anaconda now has a new D-Bus module called ``Runtime``. This module stores run-time
    configuration of the installer and provides methods for the overall installer flow control.

    .. TODO: Clarify the text as further changes are added in subsequent PRs.

    Warning: This module must always run, or anaconda crashes. Users of the following
    configuration file entries must adapt to this change:

    - ``kickstart_modules``
    - ``activatable_modules``
    - ``forbidden_modules``
    - ``optional_modules``

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4730
