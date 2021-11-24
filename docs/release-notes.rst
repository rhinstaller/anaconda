Release notes
=============

This document describes major installer-related changes in Fedora releases.

Fedora 35
#########

General changes
---------------

Limited support for braille devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Server image (boot.iso) now contains the `brltty` accessibility software.
This means that some braille output devices can be automatically detected and used.
This feature works only in text mode, started with the `inst.text` boot option.
See `the bug <https://bugzilla.redhat.com/show_bug.cgi?id=1584679>`_.

Visible warnings in initrd
^^^^^^^^^^^^^^^^^^^^^^^^^^

Installation shows critical warnings raised in Dracut/initrd again when Anaconda is
starting or when Dracut starts to timeout. This should help users to resolve installation
issues by avoiding that the important message was scrolled out too fast.
See `the bug <https://bugzilla.redhat.com/show_bug.cgi?id=1983098>`_.

Changes in the graphical interface
----------------------------------

New look of the NTP server dialog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The NTP server dialog has been redesigned. The new look uses more traditional approach to
management of lists (such as in `hexchat`). See `the pull request <https://github.com/rhinstaller/anaconda/pull/3538>`_.

- The set of controls to add a new server is no longer present. Instead, a "blank" new server
  is added by clicking an "add" button. The details can be filled in by editing the server
  in the list, as was already possible.
- The method to remove a server is now more intuitive. Users can simply click the "remove"
  button and the server is instantly removed from the list. Previously, users had to uncheck
  the "Use" checkbox for the server in the list and confirm the dialog.

New look of the root configuration screen
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The root configuration screen has been redesigned and is no longer ambiguous. All root account
options are visible only if root account is enabled. The new layout also contains text to let
users understand their choices. See `the pull request <https://github.com/rhinstaller/anaconda/pull/3511>`_.

Changes in the text interface
-----------------------------

The packaging log in ``tmux`` tabs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Add a new tab to the ``tmux`` session starting the Anaconda installer. This new tab will follows
the ``/tmp/packaging.log`` log file. This change should make it easier for users to spot software
installation errors. See `the pull request <https://github.com/rhinstaller/anaconda/pull/3472>`_.

Changes in Anaconda configuration files
---------------------------------------

Replacement of product configuration files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for the product configuration files was removed and replaced with profiles.
See `the Fedora change <https://fedoraproject.org/wiki/Changes/Replace_Anaconda_product_configuration_files_with_profiles>`_
and `the documentation <https://anaconda-installer.readthedocs.io/en/latest/configuration-files.html#profile-configuration-files>`_.

Each profile can be identified by a unique id and it can define additional options for
the automated profile detection. The profile will be chosen based on the ``inst.profile``
boot option, or based on the ``ID`` and ``VARIANT_ID`` options of the os-release files.
The profile configuration files are located in the ``/etc/anaconda/profile.d/`` directory.

The ``inst.product`` and ``inst.variant`` boot options are deprecated.

Options for Anaconda DBus module activation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We have introduced new configuration options that affect the detection and activation of
the Anaconda DBus modules. Use the ``activatable_modules`` option to specify Anaconda DBus
modules that can be activated. Use the ``forbidden_modules`` option to specify modules that
are not allowed to run. Use the ``optional_modules`` to specify modules that can fail to run
without aborting the installation.

The DBus modules can be specified by a DBus name or by a prefix of the name that ends with
an asterisk. For example::

    org.fedoraproject.Anaconda.Modules.Timezone
    org.fedoraproject.Anaconda.Addons.*

The ``addons_enabled`` and ``kickstart_modules`` options are deprecated and will be removed
in the future.

See `the pull request <https://github.com/rhinstaller/anaconda/pull/3464>`_.
