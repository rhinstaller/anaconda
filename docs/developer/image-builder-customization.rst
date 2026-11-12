Customizing the image-builder based boot.iso build
===================================================

The boot.iso is built in a container using `image-builder
<https://osbuild.org/docs/>`_ (osbuild), driven by the scripts in
``dockerfile/anaconda-iso-creator``: ``image-builder-build`` for the plain
boot.iso, and ``image-builder-build-webui`` for the Web UI variant.

The plain boot.iso build
-------------------------

``image-builder-build`` uses Fedora's built-in ``everything-network-installer``
image type by default. Set ``BOOT_ISO_VARIANT=Server`` to use
``server-network-installer`` instead. The Server type includes
``fedora-release-server``, which selects Anaconda's Server configuration.
The ISO volume label follows the selected variant (``Fedora-E-dvd-...`` or
``Fedora-S-dvd-...``), including the matching bootloader stage2 reference.
Both variants are network installers and download the installed system's
packages from repositories; this does not build an offline Server DVD.

The freshly built Anaconda RPMs are made available to it as a build-time-only
repository via ``--extra-repo``.
Missing rebuilt Anaconda RPMs or a failed copy abort the build rather than
silently falling back to distribution packages.

Image-builder's dependency solver picks the highest NEVRA across every
configured repository. Make sure the locally built Anaconda RPMs are newer
than those in the distribution repositories so the build uses them.

Selecting the boot ISO variant
-----------------------------

In a pull request comment, use::

    /build-image --boot.iso --boot-variant Server
    /build-image --boot.iso --boot-variant Server --webui

The manual **Build images** workflow has a ``boot_variant`` choice with
``Everything`` and ``Server`` options. Everything remains the default.
``--boot-variant`` only applies to boot.iso, independently of ``--live``.

For a local build, after building the Anaconda RPMs and ISO creator container::

    make -f Makefile.am container-iso-build BOOT_ISO_VARIANT=Server
    make -f Makefile.am container-webui-iso-build BOOT_ISO_VARIANT=Server

Or rebuild the RPMs and ISO together::

    scripts/testing/rebuild_iso --boot-variant Server --webui

When running the container directly, pass ``--env BOOT_ISO_VARIANT=Server``
to ``podman run``. The local output path remains ``result/iso/boot.iso``;
workflow artifact and ISO filenames include the selected variant.

The Web UI boot.iso build
-------------------------

``image-builder-build-webui`` uses the same image type as the plain build,
with a blueprint that adds Web UI packages to the Anaconda installer environment.

``customizations.installer.packages`` adds packages to the installer
environment as an additional transaction. Blueprint ``[[packages]]`` adds
packages to the system being installed instead.

Use ``ANACONDA_WEBUI_PR`` and ``COCKPIT_PR`` to include COPR builds from the
corresponding pull requests as additional build repositories.

Anaconda automatically selects Web UI when its package is installed.
