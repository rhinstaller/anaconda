:Type: Boot options
:Summary: Add inst.cert boot option for CA certificates import

:Description:

    New boot option inst.cert that imports a CA trust anchor certificate from
    the installation medium or any other disk device before kickstart or stage2
    is fetched over HTTPS was added.

    The behavior is equivalent to using the kickstart %certificate section with
    --type anchor.

:Links:
    - https://redhat.atlassian.net/browse/INSTALLER-4927
    - https://github.com/rhinstaller/anaconda/pull/7343
