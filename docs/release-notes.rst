Release notes
=============

This document describes major installer-related changes in Fedora releases.

Fedora 36
#########

General changes
---------------

The help support is unified
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The help support on RHEL and Fedora uses new mapping files with a unified format.
The mappings files are located in the root of the help directory.
For example for RHEL, they are expected to be at::

    /usr/share/anaconda/help/rhel/anaconda-gui.json
    /usr/share/anaconda/help/rhel/anaconda-tui.json

The mapping files contain data about the available help content.
The UI screens are identified by a unique screen id returned by
the ``get_screen_id`` method, for example ``installation-summary``.
The help content is defined by a relative path to a help file and
(optionally) a name of an anchor in the help file.

For example::

    {
      "_comment_": [
        "This is a comment",
        "with multiple lines."
      ],
      "_default_": {
        "file": "default-help.xml",
        "anchor": "",
      },
      "installation-summary": {
        "file": "anaconda-help.xml",
        "anchor": "",
      },
      "user-configuration": {
        "file": "anaconda-help.xml",
        "anchor": "creating-a-user-account"
      }
    }

The ``default_help_pages`` configuration option is removed. The ``helpFile`` attribute is removed
from the UI classes. See the `pull request`_ for more info.

.. _pull request:
  https://github.com/rhinstaller/anaconda/pull/3575

Changes in the graphical interface
----------------------------------

Users are administrators by default
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In the User spoke, the "Make this user administrator" checkbox is now checked by default. This
improves installation experience for users who do not know and need to rely on the default values
to guide them. See the `Users are admins by default`_ change.

.. _Users are admins by default:
   https://fedoraproject.org/wiki/Changes/Users_are_admins_by_default_in_Anaconda

Keyboard configuration is disabled on Live media with Wayland
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The keyboard switching in the Anaconda installer on the Live media did not behave as expected
on Wayland based environments (`#2016613`_). When users changed the keyboard layout configuration
that configuration was reflected in the Live environment. However, if users pressed modifier keys
(CTRL or SHIFT) the keyboard specified by the Anaconda installer was changed back for the Live
environment. That is the result of how the Wayland protocol handles keyboard layout.

To avoid this unexpected behavior Anaconda will no longer control keyboard layout configuration
of the Live systems on Wayland Live environment. The keyboard configuration set by Anaconda on
the Live environment will be reflected only to the installed system. This means that users have
to pay attention that their passwords are written by the correct layout in the installer running
inside the Live environment to be able to use the password in the system after installation.

.. _#2016613:
  https://bugzilla.redhat.com/show_bug.cgi?id=2016613

Changes in the kickstart support
--------------------------------

The `%anaconda` section is removed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The support for the deprecated `%anaconda` section is removed.
Use `Anaconda configuration files`_ instead.

.. _Anaconda configuration files:
  https://anaconda-installer.readthedocs.io/en/latest/configuration-files.html

`ANA_INSTALL_PATH` is deprecated
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ANA_INSTALL_PATH` environment variable is deprecated. The support for this variable will be
removed in future releases. Use the `/mnt/sysroot` path in your kickstart scripts instead.
See the `Installation mount points`_ documentation.

.. _Installation mount points:
  https://anaconda-installer.readthedocs.io/en/latest/mount-points.html


Changes in Anaconda options
---------------------------

`inst.nompath` is deprecated
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `inst.nompath` boot option is deprecated. It has not been doing anything useful for some
time already.


Changes in Anaconda configuration files
---------------------------------------

Saving Anaconda's data to target system
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda configuration file format now includes additional options to control
what is saved to the target system.

The options are::

    # Should we copy input kickstart to target system?
    can_copy_input_kickstart = True

    # Should we save kickstart equivalent to installation settings to the new system?
    can_save_output_kickstart = True

    # Should we save logs from the installation to the new system?
    can_save_installation_logs = True

The default values above cause no change in behavior, the new options are
only another way to configure the behavior.

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
