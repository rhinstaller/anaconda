Unified repository sourcing
===========================

The Unified feature is used automatically when Anaconda is loading installation repositories for the first time. This feature is used only if package (RPM) installation is active and the remote repository source is configured correctly. It was implemented to simplify the installation experience on systems where multiple repository sources are required to make a successful installation e.g. RHEL, CentOS Stream.

Prerequisites
-------------

* Package based installation (RPM)
* URL installation source with the ``.treeinfo`` (or ``treeinfo``) file

How this works
--------------

The Unified feature is used out of the box if the URL you want to use is pointing to a directory with ``.treeinfo`` or ``treeinfo`` file. This file contains metadata about the repository and it might also contain information about other repositories which should be used (the interesting part). The ``.treeinfo`` file may look like
::

    [variant-AppStream]
    id = AppStream
    name = AppStream
    packages = ../../AppStream/x86_64/os/Packages
    repository = ../../AppStream/x86_64/os
    type = variant
    uid = AppStream

    [variant-BaseOS]
    id = BaseOS
    name = BaseOS
    packages = ../../BaseOS/x86_64/os/Packages
    repository = ../../BaseOS/x86_64/os
    type = variant
    uid = BaseOS

Anaconda will do these steps on the first repository load:

* Read the ``.treeinfo`` / ``treeinfo`` file
* Find all the repositories in it
* Join the current source URL to relative paths of the repositories mentioned in the ``.treeinfo`` / ``treeinfo`` file
* Load these repositories as the installation source

.. note::
    This feature is designed to work only for the first time when the repositories are loaded! This is by design so we don’t change the repositories configured manually by a user.
