:Type: Anaconda configuration files
:Summary: Replace the Anaconda product configuration files with profiles (#1974819)

:Description:
    The support for the product configuration files was removed and replaced with profiles.

    Each profile can be identified by a unique id and it can define additional options for
    the automated profile detection. The profile will be chosen based on the ``inst.profile``
    boot option, or based on the ``ID`` and ``VARIANT_ID`` options of the os-release files.
    The profile configuration files are located in the ``/etc/anaconda/profile.d/`` directory.

    The ``inst.product`` and ``inst.variant`` boot options are deprecated.

:Links:
    - https://anaconda-installer.readthedocs.io/en/latest/configuration-files.html#profile-configuration-files
    - https://fedoraproject.org/wiki/Changes/Replace_Anaconda_product_configuration_files_with_profiles
    - https://github.com/rhinstaller/anaconda/pull/3388
