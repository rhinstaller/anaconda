:Type: Packaging
:Summary: Remove i686 builds

:Description:
    Anaconda is still (not explicitly) supporting i686 builds even thought
    that Fedora dropped the support a long time ago.

    Anaconda now excludes the i686 builds explicitly in Anaconda to allow
    our dependent packages drop of the i686 build.

:Links:
    - https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
    - https://github.com/coreos/fedora-coreos-tracker/issues/1716
