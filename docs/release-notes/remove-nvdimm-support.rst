:Type: Kickstart / GUI
:Summary: Remove support for NVDIMM namespaces

:Description:
    All additional support for NVDIMM is being deprecated and removed, especially the support
    for the namespace reconfiguration. However, namespaces configured in the block/storage mode
    can be still used for the installation.

    The ``nvdimm`` kickstart command is deprecated and will be removed in future releases.

:Links:
    - https://github.com/storaged-project/blivet/pull/1172
    - https://github.com/pykickstart/pykickstart/pull/469
    - https://github.com/rhinstaller/anaconda/pull/5353
