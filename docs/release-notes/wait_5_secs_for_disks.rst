:Type: Kickstart / DriverDisc / Boot
:Summary: Wait 5 secs during boot for OEMDRV devices (#2171811)

:Description:
    Because disks can take some time to appear, an additional delay of 5 seconds
    has been added.  This can be overridden by boot argument
    `inst.wait_for_disks=<value>` to let dracut wait up to <value> additional
    seconds (0 turns the feature off, causing dracut to only wait up to 500ms).
    Alternatively, if the `OEMDRV` device is known to be present but too slow to be
    autodetected, the user can boot with an argument like `inst.dd=hd:LABEL=OEMDRV`
    to indicate that dracut should expect an `OEMDRV` device and not start the
    installer until it appears.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2171811
    - https://github.com/rhinstaller/anaconda/pull/4586
