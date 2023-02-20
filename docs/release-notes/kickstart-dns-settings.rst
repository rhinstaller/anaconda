:Type: Kickstart
:Summary: New kickstart options to control DNS handling

:Description:
    There are several new options for the ``network`` kickstart command to control handling of DNS:

    - The ``--ipv4-dns-search`` and ``--ipv6-dns-search`` allow manual setting of DNS search domains. These options mirror their respective NetworkManager properties, for example:
      ``network --device ens3 --ipv4-dns-search example.com,custom-intranet-domain.biz (...)``
    - ``--ipv4-ignore-auto-dns`` and ``--ipv6-ignore-auto-dns`` allow ignoring DNS settings from DHCP. These options do not take any arguments.

    All of these ``network`` command options must be used together with the ``--device`` option.

:Links:
    - https://github.com/pykickstart/pykickstart/pull/431
    - https://github.com/rhinstaller/anaconda/pull/4519
    - https://bugzilla.redhat.com/show_bug.cgi?id=1656662
