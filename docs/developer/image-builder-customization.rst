Customizing the image-builder based boot.iso build
===================================================

The boot.iso is built in a container using `image-builder
<https://osbuild.org/docs/>`_ (osbuild), driven by the scripts in
``dockerfile/anaconda-iso-creator``: ``image-builder-build`` for the plain
boot.iso, and ``image-builder-build-webui`` for the Web UI variant.

Image-builder version and source
-------------------------------

The ISO creator container installs ``image-builder >= 89`` from the Fedora
repositories selected by ``CI_TAG``. This minimum ensures support for the
installer package customization used by the Web UI build while allowing
newer releases to be installed automatically when the container is rebuilt.
The RPM dependencies select the matching osbuild runtime packages.

If the selected repositories do not provide a sufficiently new image-builder,
the container build fails during dependency installation. The container build
logs the installed version; it can also be checked with
``image-builder version``.

The plain boot.iso build
-------------------------

``image-builder-build`` uses Fedora's built-in ``everything-network-installer``
image type (the image-builder equivalent of what lorax's
``runtime-install.tmpl`` used to build - the upstream distro definition
literally has a comment saying "Based on lorax runtime-install.tmpl").
This is a stock, unmodified image-builder build: no blueprint, no patching.
The freshly built Anaconda RPMs are made available to it as a build-time-only
repository via ``--extra-repo``.
Missing rebuilt Anaconda RPMs or a failed copy abort the build rather than
silently falling back to distribution packages.

Image-builder's dependency solver picks the highest NEVRA across every
configured repository. Make sure the locally built Anaconda RPMs are newer
than those in the distribution repositories so the build uses them.

The Web UI boot.iso build
-------------------------

There is no ``anaconda-webui`` upstream image-builder image type, so the Web
UI boot.iso is built from the same ``everything-network-installer`` type as
the plain one, with a blueprint that adds the extra packages to the Anaconda
installer environment.

``customizations.installer.packages`` adds packages to the installer
environment as an additional transaction. Blueprint ``[[packages]]`` adds
packages to the system being installed instead.

``image-builder-build-webui``:

1. Builds the boot.iso with ``image-builder-build`` (same code path as the
   plain build) while passing ``--blueprint`` - a small generated blueprint
   listing ``anaconda-webui``, ``cockpit-ws``, ``cockpit-bridge``,
   ``firefox`` and ``dbus-glib`` under
   ``customizations.installer.packages``.
2. Passes any COPR builds requested via ``ANACONDA_WEBUI_PR``/
   ``COCKPIT_PR`` to image-builder as additional ``--extra-repo``
   repositories, so those packages are picked up from the COPR too.

The resulting ISO uses the standard image-builder boot menu. Anaconda
automatically selects Web UI when its package is installed; no extra local
or remote boot menu entries are needed.

Known behavior difference: ISO volume label
---------------------------------------------

lorax was explicitly given a ``--volid`` (e.g. ``Fedora-S-dvd-x86_64-rawh``) -
partly to work around `kickstart-tests issue #448
<https://github.com/rhinstaller/kickstart-tests/issues/448>`_, where the ISO
volume label content affected network interface naming. Neither
``image-builder-build`` nor ``image-builder-build-webui`` sets a volume
label explicitly right now - the built-in ``everything-network-installer``
distro definition uses its own default (for example,
``Fedora-46-Everything-x86_64``) instead.
If NIC naming issues resurface in kickstart-tests, that's the first place to
look; ``everything-network-installer``'s blueprint does support
``customizations.iso`` (volume_id/application_id/publisher), so it can be
pinned explicitly if needed.

Rebuilding
----------

Once you've adjusted the scripts, start a boot.iso re/build, for example the
``rebuild_iso`` wrapper script::

    ./scripts/testing/rebuild_iso
    ./scripts/testing/rebuild_iso --webui

For remote Web UI access, use ``--remote PIN``. This implies ``--webui``
and uses ``mkksiso`` from the host's ``lorax`` package to add
``inst.webui.remote inst.webui.remote.pin=PIN`` to the existing boot entries,
including those in the EFI boot image::

    ./scripts/testing/rebuild_iso --remote 'my-access-pin'

The result is still ``result/iso/boot.iso``. For quick source updates, use
the same option with ``update_iso`` on an ISO that already contains Web UI::

    ./scripts/testing/update_iso --remote 'my-access-pin'

This produces the usual updated ISO with the updates image and remote boot
options applied in a single ``mkksiso`` invocation. Both scripts replace
existing remote authentication options with the supplied PIN; ``update_iso``
also accepts unrelated custom options via ``--boot-options``.
The PIN must be non-empty and does not have to be numeric. Quote it when
passing spaces or shell metacharacters on the command line.

Local builds use the scripts in your working tree. PR-comment-triggered builds
on GitHub use the committed scripts from the PR branch, so script edits must
be committed and pushed before triggering a build to test those edits.
