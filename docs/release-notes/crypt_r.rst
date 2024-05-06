:Type: Core
:Summary: Use the standalone ``crypt_r`` package for crypting passwords (rhbz#2276036)

:Description:
    The Python standard library ``crypt`` module was removed from Python 3.13+.
    Use the standalone ``crypt_r`` package maintained by the Fedora Python SIG instead.
    Support for ``crypt`` still exists as a fallback, as ``crypt_r`` is not
    available in old RHELs and Fedoras.

:Links:
    - https://bugzilla.redhat.com/2276036
    - https://github.com/rhinstaller/anaconda/pull/5628
