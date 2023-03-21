:Type: Kickstart
:Summary: Add support for OSTree native containers (#2125655)

:Description:
    Fedora is adding a new enhanced container support for the (rpm-)ostree stack to
    natively support OCI/Docker containers as a transport and delivery mechanism
    for operating system content. Anaconda now supports these containers by
    a new kickstart command `ostreecontainer`.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2125655
    - https://fedoraproject.org/wiki/Changes/OstreeNativeContainer
    - https://fedoraproject.org/wiki/Changes/OstreeNativeContainerStable
    - https://pykickstart.readthedocs.io/en/latest/kickstart-docs.html#ostreecontainer
