:Type: Kickstart
:Summary: Support certificates import via kickstart file

:Description:
    New kickstart section %certificate is supported.
    It allows users to securely embed certificates directly within
    the kickstart file. The certificates are imported both
    into the installer environment and the installed system.

:Links:
    - https://issues.redhat.com/browse/RHELBU-2913
    - https://issues.redhat.com/browse/INSTALLER-4027
    - https://github.com/rhinstaller/anaconda/pull/6045
    - https://github.com/pykickstart/pykickstart/pull/517
