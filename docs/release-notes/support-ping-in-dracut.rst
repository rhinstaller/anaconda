:Type: Dracut
:Summary: Add ping command line tool to Anaconda Dracut image (RHEL-5719)

:Description:
    Sometimes boot of the installer ISO will fail because remote source can't be reached, if this
    happens, it can be hard to debug because of the limited toolset inside the Dracut shell.
    For these reasons, we are adding a ping command line tool which can help with debugging.

:Links:
    - https://issues.redhat.com/browse/RHEL-5719
    - https://github.com/rhinstaller/anaconda/pull/5500
