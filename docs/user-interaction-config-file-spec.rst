Specification of the user interaction configuration file
========================================================

:Version:
    1.0

:Authors:
    Martin Kolman <mkolman@redhat.com>

This specification aims to establish a configuration file format that can be used
to communicate information about which installation screens have been seen by the user
during the installation. Optionally the configuration file might also contain information
about which configuration options have been changed by the user and if the user has
explicitly requested post installation setup tools to be disabled.

While this configuration file is primarily meant to be read (and potentially changed)
by *post* installation tools (such as for example Initial Setup and Gnome Initial setup),
Anaconda will take an existing configuration file into account at startup. This is meant
to accommodate tools that are run *before* Anaconda is started, such as a system-wide
language selection tool that runs before Anaconda is started and which sets language
for both Anaconda and a Live installation environment.


Configuration file location
---------------------------

The user interaction configuration file is stored in: ``/etc/sysconfig/anaconda``


General configuration file syntax
---------------------------------

The configuration file is based on the INI file de-facto standard,
eq.: key=value assignments and square bracket framed section headers.

Comments start with a hash (#) sign and need to be on a separate line.
Inline comments (eq. behind section or key/value definitions) are not supported.

For Python programs this file format can be parsed and written by the ConfigParser[0] module available
from the Python standard library. For programs written in C the GKeyFile[1] parser might be a good choice.
Comparable INI file parsing and writing modules are available for most other programming languages.

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

There are two section types:

* One special section called *General* that can contain top-level settings
  not directly corresponding to any screen.
* Other sections that correspond to Anaconda spoke screens.

  * Hubs are not represented as sections as there is nothing that can be
    directly set on a hub in Anaconda.
  * All currently visible spokes in Anaconda will be enumerated as a section headers by Anaconda in the
    configuration file. Note that this can include spokes provided by addons[2], if any Anaconda addons that provide
    additional spokes are present during the installation run.


The General section
-------------------

The *General* section is optional and is not required to be present in the config file.
At the moment it can contain only the ``post_install_tools_disabled`` key.

The ``post_install_tools_disabled`` key corresponds to using the ``firstboot --disable`` command in the installation kickstart file.
This requests that the post-installation setup tools be skipped. If this key is present and set to 1, any post-installation tools
that parse the user interaction file should first make sure the tool won't be started again on next boot, and then terminate immediately.


Naming of sections corresponding to Anaconda screens
----------------------------------------------------

All section headers not named *General* are named according to the Anaconda spoke class name. For example ``DatetimeSpoke``
or ``KeyboardSpoke``.

To get a list of all such spokes run the ``list-screens`` script from the ``scripts`` directory in the Anaconda source
code tree:

::

    git clone https://github.com/rhinstaller/anaconda
    cd anaconda/scripts
    ./list-screens

Note that this script only lists Anaconda spokes, not spokes provided by addons[2] or Initial Setup.

It is also possible to check for the *Entered spoke:* entries in the ``/tmp/anaconda.log`` file during an installation
to correlate spokes on the screen to spoke class names.


Screen section namespace
------------------------

Each section corresponding to a screen *must* contain the ``visited`` key with a value of either 1 if the user has visited
the corresponding screen or 0 if not.

Optionally each section can contain one or more keys with the ``changed_`` prefix which track if the user
has changed an option on the screen. If the option is changed by the user, the corresponding key is set
to 1. If the given option has not been changed by the user then the corresponding key can either be
omitted or set to 0.

Example:

::

    [DatetimeSpoke]
    visited=1
    changed_timezone=1
    changed_ntp=0
    changed_timedate=1

In this example the user has visited the date & time spoke and has changed the timezone & time/date,
but not the NTP settings. Note that the ``changed_ntp`` key could also be omitted as the user has not changed
the NTP options.

Another example:

::

    [KeyboardSpoke]
    visited=0

Here the user has not visited the keyboard spoke and thus could not have changed any options,
so all ``changed_*`` keys (if any) have been omitted.

Note that if a spoke section is missing, it should be assumed that the corresponding screen has not been visited.
On the other hand, if a screen *has been visited*, the section *must* be present, with the ``visited`` key being equal to 1.


Full configuration file example
-------------------------------

::

    # this is the user interaction config file

    [General]
    post_install_tools_disabled=0

    [DatetimeSpoke]
    # the date and time spoke has been visited
    visited=1
    changed_timezone=1
    changed_ntp=0
    changed_timedate=1

    [KeyboardSpoke]
    # the keyboard spoke has not been visited
    visited=0

The first section is the special section for top-level settings called *General*.
It contains only one option, ``post_install_tools_disabled``, which is in this case equal to 0
This means that post installation setup tools should proceed as usual.
In this case (being equal to 0) the ``post_install_tools_disabled`` key and the whole *General* section
might also be omitted.

Next there are two sections corresponding to two screens - ``DatetimeSpoke`` and ``KeyboardSpoke``.

The user has visited the date & time screen and has changed various options, but not the NTP settings.
On the other hand the keyboard screen has not been visited at all.


Parsing and writing the of the configuration file by Anaconda
-------------------------------------------------------------

If the user interaction file exists during Anaconda startup, it will be parsed and taken into account
when deciding which screens to show during the installation. This make it possible for secondary
installation setup tools to run before Anaconda and query the user for information.

This can be for example a tool querying the user for language settings. Then once Anaconda starts it can
skip the language selection screen as language has already been set by the tool.

Once the installation process is done, Anaconda will write out information about what screens the user has
and has not visited and optionally which settings have been changed by the user.

If Anaconda successfully parsed an existing user interaction configuration file, any valid settings present
in the file will propagate to the configuration file when it is written-out by Anaconda.

Note that comments present in the configuration file at the time Anaconda parses it might not be present
in the output file, therefore tools should not depend on comments being present or on information contained
in comments.


Parsing and writing of the configuration file by tools other than Anaconda
--------------------------------------------------------------------------

Non-Anaconda system configuration tools should also parse the user interaction file at startup and write it out
once done. All valid data already present in the configuration file should be kept and updated accordingly
(the user has visited a not-yet-visited screen, changed another option, etc.).

Non-Anaconda tools should try to keep comments present in the input file, but this is not strictly required.

Also note that a variable number of tools might be working with the configuration file in sequence, so no single tool
should expect that it is the first or last tool working with the configuration file.

Links
-----

* [0] https://docs.python.org/3/library/configparser.html
* [1] https://developer.gnome.org/glib/stable/glib-Key-value-file-parser.html
* [2] https://rhinstaller.github.io/anaconda-addon-development-guide/
