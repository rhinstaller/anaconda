:Type: Kickstart
:Summary: Deprecate RPM modularity module

:Description:
    Based on the discontinuation of RPM modularity in Fedora 39,
    we have decided to remove the RPM modularity feature in Anaconda.
    The 'module' kickstart command is no longer functional but can still
    be included in the kickstart file. However, its presence will now generate a warning.
    In a future release, this command will be completely removed,
    and its usage will result in an error.

:Links:
    - https://issues.redhat.com/browse/RHELBU-2699
    - https://issues.redhat.com/browse/INSTALLER-3909
    - https://github.com/pykickstart/pykickstart/pull/487
