:Type: Core
:Summary: Remove deprecation warnings for kernel boot options without prefix

:Description:
    Removing the deprecation warnings for kernel boot options without ``inst.``
    prefix. This was left for a couple of releases to advise users to switch
    their options to use ``inst.*`` instead. We are now removing them to not
    warn as it should be always used ``inst.`` as prefix.

:Links:
    - https://issues.redhat.com/browse/INSTALLER-2363
    - https://github.com/rhinstaller/anaconda/pull/5723/
