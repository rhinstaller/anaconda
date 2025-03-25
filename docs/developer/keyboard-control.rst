Anaconda keyboard layout control
================================

:Authors:
   Jiří Konečný <jkonecny@redhat.com>

Anaconda needs to control keyboard layouts in multiple different environments. Some of these environments are:

* boot.iso (special installation environment)
* Live ISO (running system with any Fedora/CentOS/RHEL supported Live installation environment)

It also needs to support two different types of keyboard control:

* installing user defined keyboard layout configuration into the resulting system
* control keyboard layout during the installation

Also keyboard layouts are specific to languages and have multiple variants and options which could be enabled by the user. These have to be installed correctly but also reflected correctly during the installation to avoid users to type passwords with different than expected layouts.

The Anaconda team changed the keyboard control logic in Fedora 42 with `System Wide Change <https://fedoraproject.org/wiki/Changes/Anaconda_As_Native_Wayland_Application>`_. This document will describe implementation after Fedora 42.

For the above reasons the keyboard control could be quite tricky. There are too many different environments to handle and there are specifics for these. Let's explain these parts in detail in the sections below.

Keyboard layout installation to a resulting system
--------------------------------------------------

As the system installer, Anaconda has to install the user configured keyboard layout, variant and options to the resulting system. The installed system user environment needs to be able to read this configuration and use it by Desktop Environment or Window Manager (DE/WM). To achieve this Anaconda is using systemd-localed. The installed system then takes these values as this:

* DE/WM is using localed to load the default for the user during first time login but after that it ignores the localed and using DE/WM specific ways
* the systemd-localed configuration is used in the console if no DE/WM is used

The systemd-localed configuration is stored to the resulting system. Anaconda works with systemd-localed through `DBus API <https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.locale1.html>`_. These values are stored:

* X11Layout ("cs,us")
* X11Variant (",qwerty")

  * having ``,`` as the first character means that first layout don't have any special variant
* X11Options ("grp:ctrl_shift_toggle")
* VConsoleKeymap ("us-dvorak")

The X11Layout, X11Variant and X11Options values are set by the user through the Anaconda, however, VConsoleKeymap is converted by localed from the layouts configuration or it could be set by the kickstart file. Anaconda also sets ``pc105`` as X11Model every time.

Keyboard layouts installation implementation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The layout configuration through a graphical interface is set to the ``Localization`` Anaconda module by DBus API setters. The installation of the keyboard layouts to the installed system is resolved by the installation tasks in the ``installation.py`` file in the ``localization`` Anaconda module.


Keyboard layout control of the running system (Live)
----------------------------------------------------

Installation of the user configuration is problematic but unfortunately not that problematic as controlling the keyboard configuration in the running system. Before Fedora 42, the keyboard control was solved by libxklavier library, unfortunately, this library doesn't work on Wayland environments. To make the situation worse, there is no standard way to control keyboard layouts in the Wayland environment. For example Fedora Workstation on purpose doesn't allow keyboard control to 3rd party applications by default to avoid user confusion.

To resolve this flaw of Wayland systems on Fedora 42 is proposal to require all environments running Anaconda to support systemd-localed. This support have these requirements:

* Use systemd-localed (for example by DBus API but there might be other tools)
* Reflect changes in systemd-localed to the running system

  * Ideally by listening to signals on systemd-localed configuration and reacting on these
  * Includes configuration of X11Layout, X11Variant, X11Options

Anaconda is also required to follow systemd-localed in similar way:

* Use systemd-localed DBus API
* Reflect user configuration from Anaconda to systemd-localed
* React on systemd-localed configuration changes and correctly show them to the user

  * Ignore X11Options configuration to force Options set by the user in Anaconda


.. note::

    The systemd-localed doesn't have the concept of currently selected layout or variant. For that reason it has to be resolved by changing the ordering in the list manually. So, if user changes layout (for example by keyboard shortcut) it needs to be reflected to systemd-localed in a way

    Before layout switch::

        "us,cs"
        ",qwerty"

    After switch layout to "cs (qwerty)"::

        "cs,us"
        "qwerty,"

    Beware of the X11Variant needs to also change to follow the ordering of the X11Layout!

.. note::

    After facing issues we have decided to drop requirement ``Reflect changes in running system to systemd-localed`` as it is hard to achieve from the system side.
    TODO: Add a link to release notes

Keyboard control implementation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All the Anaconda keyboard layout configuration is part of the DBus API of the ``Localization`` Anaconda DBus module. To distinguish between API for system installation and API for a running system control, the API have ``Compositor`` in the name (e.q.: ``GetCompositorLayouts`` or ``SelectNextCompositorLayout``).

Debugging of the systemd-localed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The benefit of having the middle layer with systemd-localed is a possibility to verify that everything is correctly set to the localed. A possible way to do this is use the tool busctl which is available also in the installation environment.

To list the DBus API of the localed::

    busctl --system get-property org.freedesktop.locale1 /org/freedesktop/locale1 org.freedesktop.locale1 Locale

To list current keyboard layouts, variants and options you can do this::

    busctl --system get-property org.freedesktop.locale1 /org/freedesktop/locale1 org.freedesktop.locale1 X11Layout
    busctl --system get-property org.freedesktop.locale1 /org/freedesktop/locale1 org.freedesktop.locale1 X11Variant
    busctl --system get-property org.freedesktop.locale1 /org/freedesktop/locale1 org.freedesktop.locale1 X11Options

To set the values to systemd-localed (great for testing Anaconda reaction)::

    busctl --system call org.freedesktop.locale1 /org/freedesktop/locale1 org.freedesktop.locale1 SetX11Keyboard ssssbb "cz" "pc105" "qwerty" "grp:ctrl_shift_toggle" false true
