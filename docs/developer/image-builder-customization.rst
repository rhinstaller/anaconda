Customizing the image-builder based boot.iso build
===================================================

The boot.iso is built in a container using `image-builder
<https://osbuild.org/docs/>`_ (osbuild), driven by the scripts in
``dockerfile/anaconda-iso-creator``: ``image-builder-build`` for the plain
boot.iso, and ``image-builder-build-webui`` for the Web UI variant.

The plain boot.iso build
-------------------------

``image-builder-build`` uses Fedora's built-in ``everything-network-installer``
image type (the image-builder equivalent of what lorax's
``runtime-install.tmpl`` used to build - the upstream distro definition
literally has a comment saying "Based on lorax runtime-install.tmpl").
This is a stock, unmodified image-builder build: no blueprint, no patching.
The freshly built Anaconda RPMs are made available to it as a build-time-only
repository via ``--extra-repo``.

There's a guardrail at the end of the script that extracts the built ISO,
unpacks its Anaconda rootfs image, and checks with ``rpm --root`` that the
``anaconda`` RPM actually installed there matches the one that was built -
image-builder's dependency solver has no repo-priority knob, it always just
picks the highest NEVRA across every configured repo, so without this check
a boot.iso could silently end up with the Rawhide repo's ``anaconda``
instead of the one under test. (The manifest JSON that ``--with-manifest``
would produce isn't used for this - its exact layout/filename isn't stable
enough to rely on.)

The Web UI boot.iso build
-------------------------

There is no ``anaconda-webui`` upstream image-builder image type, so the Web
UI boot.iso is built from the same ``everything-network-installer`` type as
the plain one, with a blueprint that adds the extra packages to the Anaconda
installer environment.

Older image-builder blueprints could not do that: blueprint ``[[packages]]``
only ever add packages to the system being *installed*, never to the live
Anaconda environment that runs off the ISO. Image-builder PR #2765 added a
``customizations.installer.packages`` customization which is installed into
the installer environment as an additional transaction, and that is what
``image-builder-build-webui`` uses.

``image-builder-build-webui``:

1. Builds the boot.iso with ``image-builder-build`` (same code path as the
   plain build) while passing ``--blueprint`` - a small generated blueprint
   listing ``anaconda-webui``, ``cockpit-ws``, ``cockpit-bridge``,
   ``firefox`` and ``dbus-glib`` under
   ``customizations.installer.packages``.
2. Passes any COPR builds requested via ``ANACONDA_WEBUI_PR``/
   ``COCKPIT_PR`` to image-builder as additional ``--extra-repo``
   repositories, so those packages are picked up from the COPR too.
3. Extracts the built ISO with ``xorriso`` and turns the first boot menu
   entry in the generated boot menu configs (``grub.cfg``/``isolinux.cfg``)
   into **two** separate entries - a default local one (``inst.webui``) and a
   remote one (``inst.webui inst.webui.remote``) - mirroring what the old
   lorax ``adjust-templates-for-webui.patch`` did. This is done with a small
   embedded Python script that duplicates the ``menuentry``/``label`` block,
   not a plain kernel-cmdline append. It is still needed because a blueprint
   cannot change the installer's boot arguments.
4. Reassembles the ISO with ``xorriso -boot_image any replay`` (which replays
   the original El Torito boot catalog, so only the boot configs actually
   change).

``customizations.installer.packages`` is not in a released image-builder yet.
To build a Web UI boot.iso with it, pass the image-builder pull request number
to the ISO build via the ``IMAGE_BUILDER_PR`` environment variable (e.g.
``IMAGE_BUILDER_PR=2765``): ``image-builder-build`` then replaces the
container's image-builder with the one from that PR's packit COPR before
building. This mirrors the ``ANACONDA_WEBUI_PR``/``COCKPIT_PR`` handling and
keeps no PR number baked into the scripts; once a release with the feature
lands in the distro repos, just leave ``IMAGE_BUILDER_PR`` unset.

Known behavior difference: ISO volume label
---------------------------------------------

lorax was explicitly given a ``--volid`` (e.g. ``Fedora-S-dvd-x86_64-rawh``) -
partly to work around `kickstart-tests issue #448
<https://github.com/rhinstaller/kickstart-tests/issues/448>`_, where the ISO
volume label content affected network interface naming. Neither
``image-builder-build`` nor ``image-builder-build-webui`` sets a volume
label explicitly right now - the built-in ``everything-network-installer``
distro definition uses its own default (currently ``"Everything"``) instead.
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

Note that if you want to build images on the GitHub infra via PR comment
trigger, *don't forget to check in also the script changes*!
