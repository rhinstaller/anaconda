:Type: Kickstart
:Summary: The installation program now correctly processes the proxy configuration (#2177219)

:Description:
    Previously, the installation program did not correctly process the ``--proxy`` option of the
    ``url`` Kickstart command or ``inst.proxy`` kernel boot parameter. As a consequence, you could
    not use the specified proxy to fetch the installation image. With this update, the issue
    is fixed and proxy works as expected.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2177219
    - https://github.com/rhinstaller/anaconda/pull/4828
