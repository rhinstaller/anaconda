Customizing the image-builder based boot.iso build
===================================================

The boot.iso is built in a container using `image-builder
<https://osbuild.org/docs/>`_ (osbuild), driven by the scripts in
``dockerfile/anaconda-iso-creator``: ``image-builder-build`` for the plain
boot.iso, and ``image-builder-build-webui`` for the Web UI variant.

The plain boot.iso build
-------------------------

``image-builder-build`` uses Fedora's built-in ``everything-network-installer``
image type.
The freshly built Anaconda RPMs are made available to it as a build-time-only
repository via ``--extra-repo``.
Missing rebuilt Anaconda RPMs or a failed copy abort the build rather than
silently falling back to distribution packages.

Image-builder's dependency solver picks the highest NEVRA across every
configured repository. Make sure the locally built Anaconda RPMs are newer
than those in the distribution repositories so the build uses them.

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
