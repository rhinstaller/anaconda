Anaconda sysconfig file
=======================

This specification aims to establish a configuration file format that can be used to configure
post-installation tools. This configuration file is primarily meant to be read (and potentially
changed) by *post* installation tools (such as for example Initial Setup and Gnome Initial setup).

Configuration file location
---------------------------

The Anaconda sysconfig file is stored in: ``/etc/sysconfig/anaconda``

General configuration file syntax
---------------------------------

The configuration file is based on the INI file de-facto standard,
eq.: key=value assignments and square bracket framed section headers.

Comments start with a hash (#) sign and need to be on a separate line. Inline comments
(eq. behind section or key/value definitions) are not supported.

For Python programs this file format can be parsed and written by the ConfigParser[0] module
available from the Python standard library. For programs written in C the GKeyFile[1] parser might
be a good choice. Comparable INI file parsing and writing modules are available for most other
programming languages.

Example:

::

    # comment example - before the section headers

    [section_1]
    # comment example - inside section 1
    key_a_in_section1=some_value
    key_b_in_section1=some_value

    [section_2]
    # comment example - inside section 2
    key_a_in_section2=some_value

Boolean values are marked with 1 for true and 0 for false.

Example:

::

    true_key=1
    false_key=0

Toplevel namespace
------------------

The toplevel configuration file namespace can only contain section headers.

There is only one special section called *General* that can contain top-level settings not
directly corresponding to any screen.

The General section
-------------------

The *General* section is optional and is not required to be present in the config file.
At the moment it can contain only the ``post_install_tools_disabled`` key.

The ``post_install_tools_disabled`` key corresponds to using the ``firstboot --disable`` command
in the installation kickstart file. This requests that the post-installation setup tools be
skipped. If this key is present and set to 1, any post-installation tools that parse the Anaconda
sysconfig file should first make sure the tool won't be started again on next boot, and then
terminate immediately.

Full configuration file example
-------------------------------

::

    # This is the Anaconda sysconfig file.

    [General]
    post_install_tools_disabled=0

The specified section is the special section for top-level settings called *General*. It contains
only one option, ``post_install_tools_disabled``, which is in this case equal to 0 This means
that post installation setup tools should proceed as usual. In this case (being equal to 0) the
``post_install_tools_disabled`` key and the whole *General* section might also be omitted.

Parsing and writing of the configuration file by tools other than Anaconda
--------------------------------------------------------------------------

Non-Anaconda system configuration tools should parse the Anaconda sysconfig file at startup and
write it out once done. All valid data already present in the configuration file should be kept
and updated accordingly.

Non-Anaconda tools should try to keep comments present in the input file, but this is not strictly
required.

Also note that a variable number of tools might be working with the configuration file in sequence,
so no single tool should expect that it is the first or last tool working with the configuration
file.

Links
-----

* [0] https://docs.python.org/3/library/configparser.html
* [1] https://developer.gnome.org/glib/stable/glib-Key-value-file-parser.html
* [2] https://rhinstaller.github.io/anaconda-addon-development-guide/
