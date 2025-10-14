Using patched Lorax templates for a boot.iso build
==================================================

There are cases when we need to test changes to the Lorax templates used to build the boot.iso. The reason could be general debugging or possibly testing of changes before we submit them to the Lorax upstream.

The boot.iso is built in a container, using upstream Lorax templates. We will apply a patch to these templates so that our changes are reflected in the templates used for the image build.

Start by cloning Anaconda and Lorax::

    git clone https://github.com/rhinstaller/anaconda
    git clone https://github.com/weldr/lorax
    cd lorax

Edit the templates, for example the install template::

    vim share/templates.d/99-generic/runtime-install.tmpl

Create a patch file from the changes::

    git diff > install_mc.patch

The example patch looks like this::

    diff --git a/share/templates.d/99-generic/runtime-install.tmpl b/share/templates.d/99-generic/runtime-install.tmpl
    index 2fcb697e..b198c131 100644
    --- a/share/templates.d/99-generic/runtime-install.tmpl
    +++ b/share/templates.d/99-generic/runtime-install.tmpl
    @@ -107,6 +107,9 @@ installpkg kbd kbd-misc
     ## required for anaconda-dracut (img-lib etc.)
     installpkg tar xz curl bzip2

    +## everybody needs mc
    +installpkg mc
    +
     ## basic system stuff
     installpkg rsyslog

Copy the patch file to your Anaconda checkout, to the ``dockerfile/anaconda-iso-creator`` folder::

    cd ..
    cp lorax/install_mc.patch anaconda/dockerfile/anaconda-iso-creator/

Edit the ``dockerfile/anaconda-iso-creator/Dockerfile`` file & add a new ``COPY`` line to include your patch to the container.

It should look like this::

    diff --git a/dockerfile/anaconda-iso-creator/Dockerfile b/dockerfile/anaconda-iso-creator/Dockerfile
    index 25e2b09c73..b81ec37b00 100644
    --- a/dockerfile/anaconda-iso-creator/Dockerfile
    +++ b/dockerfile/anaconda-iso-creator/Dockerfile
    @@ -43,6 +43,7 @@ RUN set -ex; \
     COPY ["lorax-build", "/"]
     COPY ["lorax-build-webui", "/"]
     COPY ["adjust-templates-for-webui.patch", "/"]
    +COPY ["install_mc.patch", "/"]

     RUN mkdir /lorax /anaconda-rpms /images

Next you need to edit the boot.iso build script to patch the templates & use the patched templates::

    diff --git a/dockerfile/anaconda-iso-creator/lorax-build b/dockerfile/anaconda-iso-creator/lorax-build
    index b940b953b7..429b027932 100755
    --- a/dockerfile/anaconda-iso-creator/lorax-build
    +++ b/dockerfile/anaconda-iso-creator/lorax-build
    @@ -36,12 +36,16 @@ mkdir -p $REPO_DIR
     cp -a $INPUT_RPMS/* $REPO_DIR || echo "RPM files can't be copied!"  # We could just do the build with official repositories only
     createrepo_c $REPO_DIR

    +cp -r /usr/share/lorax/templates.d/ /lorax/
    +patch -p2 -i /install_mc.patch
    +
     # build boot.iso with our rpms
     . /etc/os-release
     # The download.fedoraproject.org automatic redirector often selects download-ib01.f.o. for GitHub's cloud, which is too unreliable; use a mirror
     # The --volid argument can cause different network interface naming: https://github.com/rhinstaller/kickstart-tests/issues/448
     lorax -p Fedora -v "$VERSION_ID" -r "$VERSION_ID" \
           --volid Fedora-S-dvd-x86_64-rawh \
    +      --sharedir ./templates.d/99-generic/ \
           -s http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/ \
           -s file://$REPO_DIR/ \
           "$@" \

And that should be it! Now you just need to start a boot.iso re/build, for example the ``rebuild_iso`` wrapper script::

    ./scripts/testing/rebuild_iso

Note that if you want to build images on the GitHub infra via PR comment trigger, *don't forget to check in also the patch file* !

Example PR
----------

An example PR demonstrating this in action has been created:

https://github.com/rhinstaller/anaconda/pull/6528

This might end up outdated over time but should hopefully still illustrate how all the bits and pieces fit together in practice.

