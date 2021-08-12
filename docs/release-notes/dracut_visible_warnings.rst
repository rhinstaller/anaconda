:Type: Initial RAM disk (initrd)
:Summary: Make critical installer warnings in Dracut/initrd more visible (#1983098)

:Description:
    Installation shows critical warnings raised in Dracut/initrd again when Anaconda is
    starting or when Dracut starts to timeout. This should help users to resolve installation
    issues by avoiding that the important message was scrolled out too fast.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=1983098#
    - https://github.com/rhinstaller/anaconda/pull/3533
