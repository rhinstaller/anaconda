:Type: Network
:Summary: Stop creating default network profiles for unconfigured devices

:Description:
    Traditionally Anaconda created default persistent network profiles (ifcfg files or keyfiles) for every supported wired network device. Since the change only devices configured during installation (via boot options, kickstart, or in UI) will have persistent profile created on the installed system.

:Links:
    - https://issues.redhat.com/browse/INSTALLER-3088
    - https://github.com/rhinstaller/anaconda/pull/6787
