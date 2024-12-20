Anaconda configuration files
============================

The installer loads its default configuration from the Anaconda configuration files. The
configuration can be modified by kernel arguments and cmdline options and the result is written
into a runtime configuration file. The configuration is not supposed to change after that.
The runtime configuration file is loaded by the Anaconda DBus modules when they are started.
It means that all Anaconda processes are running with the same configuration.


.. note::

    The software selected for the installation doesn't change the Anaconda configuration
    and profiles in any way.

.. note::

    The ``interactive-defaults.ks`` file will be replaced by the Anaconda configuration
    files in the future. Kickstart files should be used only for the automatic installation.

File structure
--------------

The Anaconda configuration files are written in the INI format that can be processed by
`configparser <https://docs.python.org/3/library/configparser.html>`_. The files consist
of sections, options and comments. Each section is defined by a ``[section]`` header. Each
option is defined by a key and optionally a value separated by the ``=`` sign. Each comment
has to start on a new line prefixed by the ``#`` character.

See an example of a section::

    [Storage Constraints]

    # Minimal size of the total memory.
    min_ram = 320 MiB

    # Should we recommend to specify a swap partition?
    swap_is_recommended = False

    # Recommended minimal sizes of partitions.
    # Specify a mount point and a size on each line.
    min_partition_sizes =
        /      250 MiB
        /usr   250 MiB

    # Required minimal sizes of partitions.
    # Specify a mount point and a size on each line.
    req_partition_sizes =


The supported sections and options are documented in the default configuration file.

Default configuration file
--------------------------

The default configuration file provides a full default configuration of the installer.
It defines and documents all supported sections and options. The file is located at
``/etc/anaconda/anaconda.conf``:

.. include:: ../data/anaconda.conf
    :code: ini

Profile configuration files
---------------------------

The profile configuration files allow to override some of the configuration options for
specific profiles and products. The files are located at ``/etc/anaconda/profile.d/``.

.. note::

    Anaconda previously used so called install classes for the product-specific configuration.
    Install classes were completely removed and replaced by the profile configuration files.
    These configuration files used to be called product configuration files for some time.

Profile identification
^^^^^^^^^^^^^^^^^^^^^^

Each profile has a unique profile id. It is a lower-case string with no spaces that identifies
the profile. The id can be arbitrary, but the convention is to use the name of the configuration
file (for example, ``fedora-server``).

Profile detection
^^^^^^^^^^^^^^^^^

The profile can be specified by the ``inst.profile`` boot option or the ``--profile`` cmdline
option. Based on the provided profile id, the installer will look up the right configuration
file in the ``/etc/anaconda/profile.d/`` directory.

Otherwise, the profile will be chosen based on the ``os-release`` values of the installation
environment. These values are provided by the ``/etc/os-release`` or ``/usr/lib/os-release`` file
containing operating system identification data. The profile can define os and variant ids
that should match ``ID`` and ``VARIANT_ID`` options of the ``os-release`` files. The installer
will use a profile with the best match.

File structure
^^^^^^^^^^^^^^

Profile configuration files have one or two extra sections that describe the profile.

The ``[Profile]`` section defines a profile id of the profile. Optionally, it can specify a
profile id of a base profile. For example, ``fedora`` is a base profile of ``fedora-server``.

We support a simple inheritance of profile configurations. The installer loads configuration files
of the base profiles before it loads the configuration file of the specified profile. For example,
it will first load the configuration for ``fedora`` and then the configuration for ``fedora-server``.

.. note::

    We are not going to support multiple inheritance. It would significantly increase the
    complexity of the profile configuration files in an unintuitive way. You can easily compare
    two configuration files and verify the parts they are supposed to share. We do that in our
    unit tests.

The ``[Profile Detection]`` defines the operating system id and the variant id that should match
``os-release`` values of the expected installation environment. It is useful for assigning
the profile to a specific product (for example, Fedora Server). This section is optional.

.. note::
    We are not going to support wildcards in the profile detection. This used to be supported
    in install classes and it caused a lot of problems. Without the wildcards, we will always
    match at most one profile.

See an example of the profile configuration file for Fedora Server::

    # Anaconda configuration file for Fedora Server.

    [Profile]
    # Define the profile.
    profile_id = fedora-server
    base_profile = fedora

    [Profile Detection]
    # Match os-release values.
    os_id = fedora
    variant_id = server

    [Payload]
    # Change payload-related options.
    default_environment = server-product-environment

    [Storage]
    # Change storage-related options.
    file_system_type = xfs
    default_scheme = LVM


Custom configuration files
--------------------------

The custom configuration files allow to override some of the configuration options for specific
installations. The files are located at ``/etc/anaconda/conf.d/``.

The installer finds all files with the ``.conf`` extension in the ``/etc/anaconda/conf.d/``
directory, sorts them by their name and loads them in this order. These files are loaded after
the profile configuration files, so they have a higher priority.

For example, the initial setup installs the ``10-initial-setup.conf`` file with a custom
configuration.

.. note::

    All configuration files have to be loaded before the installer starts to parse the
    kickstart file, so it is not possible to generate a configuration file in the ``%pre``
    section of the kickstart file. Please, use ``updates.img`` or ``product.img`` instead.

Runtime configuration file
--------------------------

The runtime configuration file is a temporary file that provides a full configuration of the
current installer run. It is generated by the installer and it exists only during its lifetime.
The file is located at ``/run/anaconda/anaconda.conf``.

The runtime configuration file is loaded by the Anaconda DBus modules when they are started.
It allows us to run all Anaconda processes with the same configuration.

The installer makes the following steps to create the runtime configuration file. The
configuration is not supposed to change after that.

1. Load the default configuration file from ``/etc/anaconda/anaconda.conf``.
2. Load the selected profile configuration files from ``/etc/anaconda/profile.d/*.conf``.
3. Load the custom configuration files from ``/etc/anaconda/conf.d/*.conf``.
4. Apply the kernel arguments.
5. Apply the cmdline options.
6. Generate the runtime configuration file ``/run/anaconda/anaconda.conf``.

Python representation
---------------------

The Anaconda configuration is represented by the ``conf`` object from
``pyanaconda.core.configuration.anaconda``. The configuration sections are represented by
properties of the ``conf`` object. The configuration options are represented by properties
of the section representation. All these properties are read-only.

The ``conf`` object is initialized on the first import. It loads the runtime configuration file,
if it exists, otherwise it loads the default configuration file. Its main purpose is to provide
access to the configuration of the current installer run.

It is safe to use the ``conf`` object in the Anaconda DBus modules and in any other Python
processes that are started after a runtime configuration file has been generated.

See an example of a Python code::

    from pyanaconda.core.configuration.anaconda import conf

    # Is Anaconda in the debugging mode?
    print(conf.anaconda.debug)

    # Is the type of the installation target hardware?
    print(conf.target.is_hardware)

    # A path to the system root of the target.
    print(conf.target.system_root)

