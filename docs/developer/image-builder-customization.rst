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

Why the Web UI boot.iso can't be "just a blueprint"
-----------------------------------------------------

Unlike lorax, where any package could be added with a simple ``-i`` flag,
image-builder blueprints cannot add packages to the Anaconda installer
environment itself (``package_sets.installer`` in image-builder's distro
definition) for *any* Fedora image type - blueprint ``[[packages]]`` only
ever add packages to the system being *installed*, never to the live
Anaconda environment that runs off the ISO. There's also no supported,
non-experimental way to define a brand new image type (image-builder's
``IMAGE_BUILDER_EXPERIMENTAL=yamldir=...`` override replaces *all* of
image-builder's built-in distro data, not just adds one type, and upstream
explicitly says it "should never be used in production").

Since there is no ``anaconda-webui`` upstream image-builder type to begin
with, ``image-builder-build-webui`` instead:

1. Builds the plain boot.iso with ``image-builder-build`` (same guardrail as
   above also applies here, for both ``anaconda`` and ``anaconda-webui``).
2. Extracts it with ``xorriso``.
3. Finds the Anaconda rootfs image inside it (``erofs`` or ``squashfs``,
   whichever the distro definition currently uses), unpacks it, and installs
   ``anaconda-webui``, ``cockpit-ws``, ``cockpit-bridge``, ``firefox`` and
   ``dbus-glib`` into it with ``dnf --installroot`` (using the same repos as
   the main build, plus any COPR builds requested via ``ANACONDA_WEBUI_PR``/
   ``COCKPIT_PR``).
4. Repacks the rootfs image, then turns the first boot menu entry in the
   generated boot menu configs (``grub.cfg``/``isolinux.cfg``) into **two**
   separate entries - a default local one (``inst.webui``) and a remote one
   (``inst.webui inst.webui.remote``) - mirroring what the old lorax
   ``adjust-templates-for-webui.patch`` did. This is done with a small
   embedded Python script that duplicates the ``menuentry``/``label`` block,
   not a plain kernel-cmdline append.
5. Reassembles the ISO with ``xorriso -boot_image any replay`` (which replays
   the original El Torito boot catalog, so only the rootfs image and the
   boot configs actually change).

This is intentionally the *only* place this build patches anything after
the fact - the plain boot.iso stays a pure, unmodified image-builder build.
If anaconda-webui ever gets a proper upstream image-builder image type, this
whole post-processing step should be dropped in favor of that.

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
