:Type: Anaconda configuration options
:Summary: Add new configuration options for the Anaconda DBus module activation

:Description:
    We have introduced new configuration options that affect the detection and activation of
    the Anaconda DBus modules. Use the ``activatable_modules`` option to specify Anaconda DBus
    modules that can be activated. Use the ``forbidden_modules`` option to specify modules that
    are not allowed to run. Use the ``optional_modules`` to specify modules that can fail to run
    without aborting the installation.

    The DBus modules can be specified by a DBus name or by a prefix of the name that ends with
    an asterisk. For example::

        org.fedoraproject.Anaconda.Modules.Timezone
        org.fedoraproject.Anaconda.Addons.*

    The ``addons_enabled`` and ``kickstart_modules`` options are deprecated and will be removed
    in the future.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/3464
