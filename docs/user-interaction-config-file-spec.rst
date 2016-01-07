Specification of the user interaction configuration file
========================================================

:Version:
    1.0

:Authors:
    Martin Kolman <mkolman@redhat.com>

This specification aims to establish a configuration file format, that can be used
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


General configuration file systax
---------------------------------

The configuration file is based on the INI file de-facto standard,
eq.: key=value assignments and square bracket framed section headers.

Example:

::

    top_level_key=some_value

    [section_1]
    key_a_in_section1=some_value
    key_b_in_section1=some_value

    [section_2]
    key_a_in_section2=some_value

Boolean values are marked with 1 for true and 0 for false.

Example:

::

    true_key=1
    false_key=0


Toplevel namespace
------------------

The toplevel configuration file namespace can only contain the
``post_install_tools_disabled`` key and section headers.

The ``post_install_tools_disabled`` key corresponds to using ``firstboot --disable`` command in the
installation kickstart, that requests the post installation setup tools to be skipped. If this key is present
and set to true, then any post installation tools that parses the user interaction file should make sure
it won't be started again and then terminate immediately.

Section headers each correspond to a spoke screen shown in Anaconda. Hubs are not represented as section
as there is nothing that can be directly set on a hub in Anaconda.
All currently visible spokes in Anaconda will be enumerated as a section headers by Anaconda in the
configuration file. Note that this can include spokes provided by addons, if any Anaconda addons that provide
additional spokes are present during the installation run.


Section naming
--------------

Section headers are named according to the Anaconda spoke class name. For example ``DatetimeSpoke``
or ``KeyboardSpoke``.


Section namespace
-----------------

Each section *must* contain the ``visited`` key with a value of either true if the user has visited
the corresponding screen or false if not.

Optional each section can contain one or more keys with the ``changed_`` prefix which track if the user
has changed an option on the screen. If the option is changed by the user, the corresponding key is set
to true. If the given option has not been changed by the user then the corresponding key can either be
omitted or set to false.

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


Full configuration file example
-------------------------------

::

    post_install_tools_disabled=0

    [DatetimeSpoke]
    visited=1
    changed_timezone=1
    changed_ntp=0
    changed_timedate=1

    [KeyboardSpoke]
    visited=0

On the first line of the example the ``post_install_tools_disabled`` is equal to false, which means that
post installation setup tools should proceed as usual. In this case the ``post_install_tools_disabled`` key
might also be omitted.

Next there are two sections corresponding to two screens - ``Datetimespoke`` and ``KeyboardSpoke``.

The user has visited the date & time screen and has changed various options, but not the NTP settings.
On the other hand the keyboard screen has not been visited at all.


Parsing and writing the of the configuration file by Anaconda
-------------------------------------------------------------

If the user interaction file exists during Anaconda startup, it will be parsed and taken into account
when deciding which screens to show during the installation. This make it possible for secondary
installation setup tools to run before Anaconda and query the user for information.

This can be for example a tool querying the user for language settings. Then once Anaconda starts it can
skip the language selection screen as language has already been set by the tool.

Once the installation process is done Anaconda will write out information about what screens the user has
and has not visited and optionally which settings have been changed by the user.

If Anaconda successfully parsed an existing user interaction configuration file, any valid settings present
in the file will propagate to the configuration file when it is written-out by Anaconda.


Parsing and writing of the configuration file by tools other than Anaconda
--------------------------------------------------------------------------

Non-Anaconda system configuration tools should also parse the user interaction file at startup and write it out
once done. All valid data already present in the configuration file should be kept and updated accordingly
(the user has visited a not yet visited screen screen, changed another option, etc.).

Also note that a variable number of tools might be working with the configuration file in sequence, so no single tool
should expect that it is the first or last tool working with the configuration file.
