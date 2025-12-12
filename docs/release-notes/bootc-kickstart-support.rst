:Type: Core / Kickstart
:Summary: Add bootc kickstart command support

:Description:
    Anaconda now supports the new ``bootc`` kickstart command to install bootc-based
    bootable containers. This command is similar to the existing ``ostreecontainer``
    command, but uses the ``bootc`` tool to handle both filesystem population and
    bootloader configuration.

    Usage example::

        bootc --source-imgref=registry:quay.io/fedora/fedora-bootc:rawhide

    Note that there are some current limitations, such as lack of support for
    partitioning setups spanning multiple disks, arbitrary mount points, or installation
    from authenticated registries.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/6298
    - https://issues.redhat.com/browse/INSTALLER-4024

