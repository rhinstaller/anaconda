:Type: Storage configuration
:Summary: Change the default disk label type

:Description:
    Use the `inst.disklabel` boot option to specify a preferred disk label type. Specify
    `gpt` to prefer creation of GPT disk labels. Specify `mbr` to prefer creation of MBR
    disk labels if supported. The `inst.gpt` boot option is deprecated and will be removed
    in future releases.

    The default value of the preferred disk label type is specified by the `disk_label_type`
    option in the Anaconda configuration files. The `gpt` configuration option is no longer
    supported.

    Fedora Linux systems installed on legacy x86 BIOS systems should get GPT partitioning by
    default instead of legacy MBR partitioning. This should be a new default for all products.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4232
    - https://fedoraproject.org/wiki/Changes/GPTforBIOSbyDefault
