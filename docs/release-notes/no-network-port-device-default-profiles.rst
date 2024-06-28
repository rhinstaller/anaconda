:Type: Network
:Summmary: Do not create default network profiles for network port devices

:Description:
    Traditionally Anaconda creates default persistent network profiles (ifcfg files or keyfiles) for every supported wired network device.  We would like to move towards creating profiles only for devices explicitly configured by installer. As a step in this direction do not create such files for devices used as ports of a virtual device (for example bond device) configured by installer, unless they were explicitly configured separately (for example in early stage from boot options).

:Links:
    - https://issues.redhat.com/browse/RHEL-38451
    - https://github.com/rhinstaller/anaconda/pull/5703
