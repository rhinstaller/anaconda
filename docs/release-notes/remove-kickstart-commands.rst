:Type: Kickstart
:Summary: Remove and deprecate selected kickstart commands and options

:Description:
    The following deprecated kickstart commands and options are removed:

    - ``autostep``
    - ``method``
    - ``logging --level``
    - ``repo --ignoregroups``

    The following kickstart options are deprecated:

    - ``timezone --isUtc``
    - ``timezone --ntpservers``
    - ``timezone --nontp``
    - ``%packages --instLangs``
    - ``%packages --excludeWeakdeps``

:Links:
    - https://github.com/rhinstaller/anaconda/pull/5436
    - https://github.com/rhinstaller/anaconda/pull/5438
    - https://github.com/pykickstart/pykickstart/pull/475
