Image Creation
==============

:Authors:
    Anaconda Developers <anaconda-devel-list@redhat.com>
    Martin Kolman <mkolman@redhat.com>

Sometimes during Anaconda development and/or debugging it is necessary
to build a full installation image to properly test and validate changes.

Building a custom Anaconda package
----------------------------------

Both Live image and boot iso creation expects you to have the artifacts you want to to include
in the form of RPM packages. So if we want to test custom Anaconda changes, we need to first build a custom
Anaconda package that includes our changes.

In this example we will start by cloning the Anaconda repository and doing a new local package build.
In general you should be able to do the same thing from your existing Anaconda checkout with your changes.

::

    git clone https://github.com/rhinstaller/anaconda/
    cd anaconda

Now you can apply any changes to the source code, switch branches, etc.

Next we build a new Anaconda package containing the changes, with a custom build
number to easily tell it apart from regular package builds:

::

    vim configure.ac

Find the following line, it should look like this:

::

    AC_INIT([anaconda], [30.13], [anaconda-devel-list@redhat.com])

And  change it to:

::

    AC_INIT([anaconda], [1000.1000], [anaconda-devel-list@redhat.com])

This should result in a package with major and minor version 1000,
which should be easy to tell apart from regular packages and should
always be preferred the version available in the normal repositories.

Install build dependencies of the Anaconda package:

::

    sudo dnf install $(./scripts/testing/dependency_solver.py)

Create a local package build of Anaconda with the changes:

::

    mkdir rpms
    make clean
    ./autogen.sh
    ./configure
    rpmbuild anaconda.spec --build-in-place -bb --define "_rpmdir $(pwd)/rpms"

Turn the  `rpms` directory into a regular RPM repository:

::

    createrepo_c rpms

Don't forget to rerun this when you rebuild the package, bump the version, etc.


Setting up Mock
---------------

This guide uses a Mock chroot for both the Live image and boot iso build,
so the this section will describe how to get Mock setup and ready for use.


First we install the necessary tooling:

::

    sudo dnf install mock

Setup your current user to be able to use mock:

::

    usermod -a -G mock <your username>

Setup the Mock environment:

::

    mock -r fedora-rawhide-x86_64 --init
    mock -r fedora-rawhide-x86_64 --install lorax-lmc-novirt

We are using the Rawhide mock config, use other configs as appropriate.

Enable Networking in Mock - by default there is no network access in Mock.
Set config_opts['rpmbuild_networking'] to True if you are using systemd-nspawn.

::

    sudo vim /etc/mock/site-defaults.cfg

If your system is using SELinux, it needs to be set to Permissive mode while running
live media creator/Lorax.

Note: This is being worked on in Lorax so that it can work correctly with SELinux enabled.

::

    sudo setenforce 0

Live image
----------

One might need to build a custom live image both to test changes in Anaconda
affecting the live environment as well as testing changes in the kickstarts
used to generate the live images.

To build a live image with a custom version of Anaconda we need:

- Anaconda package with our custom changes
- the image build tooling
- fedora live kickstarts

Start by reading the **Setting up Mock** section and **Building a custom Anaconda package** sections.

Next we install the necessary tooling on the local system:

::

    sudo dnf install pykickstart rpm-build mock

Create a working directory for the image creation & switch to it:

::

    mkdir live_build
    cd live_build

Clone the Fedora live kickstarts repository:

::

    git clone https://pagure.io/fedora-kickstarts.git

The default branch has kickstarts for Rawhide, you can switch to a release branch
or apply your own changes to the kickstarts at this point.

The Fedora live kickstarts are generally composed from a set of
templates and need to be first *flattened* by the Pykickstart
provided `ksflatten` tool to be useful. We will build the Fedora
Workstation kickstart but any other variant can be build in a
similar way:

::

    cd fedora-kickstarts
    ksflatten --config fedora-live-workstation.ks -o flat-fedora-live-workstation.ks
    cd ..

Next we will build the live image with live media creator in Mock.

Copy the flat kickstart into the Mock chroot:

::

    mock -r fedora-rawhide-x86_64 --copyin ../fedora-kickstarts/flat-fedora-live-workstation.ks /

Copy the repository with custom Anaconda RPMs to the Mock chroot (we assume the Anaconda checkout is in
the same folder as the live_build working directory):

::
    mock -r fedora-rawhide-x86_64 --copyin anaconda/rpms /

Now switch to a shell running in the Mock and build the live image. The ``--old-chroot`` flag
is important or else Lorax will fail to start the installation.

::

    mock -r fedora-rawhide-x86_64 --shell --old-chroot


Now start a live media build by live media creator that makes use of our custom Anaconda packages:

**NOTE:** There is currently a bug in Anaconda preventing ``--addrepo`` from working in this way, but it should
be fixed soon.

::
    livemedia-creator --make-iso --iso-only --no-virt --ks flat-fedora-live-workstation.ks --anaconda-arg="--addrepo=custom_anaconda,file:///rpms" --resultdir results --iso-name custom_live

Explanation of the used options:

``--make-iso``
    Create a live iso.

``--iso-only``
    We only need the bootable live iso, not the other artifacts.

``--no-virt``
    Run directly as an application (in the Mock environment) instead of running the installation
    in a VM. This also makes it easier to inject our custom Anaconda RPMs as we can point Anaconda
    to local file system paths.

``--ks``
    Path to the kickstart file to use when building the live image.

``--anaconda-arg="--addrepo=custom_anaconda,file:///rpms"``
    Use the ``--anaconda-arg`` LMC option to forward Anaconda the ``--addrepo=custom_anaconda,file:///rpms"`` so that
    our custom Anaconda RPMs from the local repo folder we have copied into the Mock environment a few steps above
    are used when the live image is generated.

``--resultdir results``
    We use this option to get a static path for the resulting image we can use to easily fetch the image out
    of the Mock chroot. Note that LMC will refuse to run if the folder exists, so you might need to rename
    or remove it if you do multiple LMC runs.

``--isoname results``
    Name the custom image for convenience.

See the `live media creator reference <https://weldr.io/lorax/livemedia-creator.html#livemedia-creator-cmdline-arguments>`
for detailed documentation of all the available command line options.

Now exit the Mock shell and copy the custom live image out of the chroot:

::

   mock -r fedora-rawhide-x86_64 --copyout /results/images/custom_live.iso .

And that's it, you now have a live image containing your custom Anaconda package build with your changes. Note that
the Anaconda installed in the Mock chroot is used to **build** the image. If you want to test changes influencing
live image generation you need to also install your custom Anaconda RPMs to the Mock environment.

Boot iso
--------

The boot iso is basically a minimal bootable Linux distribution with just enough software to launch Anaconda and
install an OS to a target. Unlike the Live image, which is created by Anaconda installing packages into a folder
based on an input kickstart, boot iso is created by Lorax  without running Anaconda. Lorax has a set of
templates, both for what to include and what to include, which are used to feed a DNF dirinstall run and then selectively
cleanup the result.

Generally one might want to do a custom boot iso to test packaging changes, changes in Lorax templates or in Lorax itself.

We will build the boot iso in a Mock chroot, so start by by reading the **Setting up Mock** section and
**Building a custom Anaconda package** sections.

Then we copy the repository with custom Anaconda RPMs to the Mock chroot (we assume the Anaconda checkout is in
current working directory):

::
    mock -r fedora-rawhide-x86_64 --copyin anaconda/rpms /

Next we run Lorax to generate a boot iso while instructing it to use our custom repo with Anaconda packages.
The same mechanism can be used to inject any other packages as well.

::
    mock -r fedora-rawhide-x86_64 --old-chroot --chroot "lorax -p Fedora-Server -v rawhide -r rawhide --buildarch x86_64 -s https://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/ -s file:///rpms ./output"

Explanation of the arguments used for the Lorax run:

``-p Fedora-Server``
    Fedora Server product name.

``-v rawhide``
    Rawhide version identifier.

``-r rawhide``
    Rawhide release information.

The product name, version and release serve to configure what Lorax templates to use and to set various user visible distro names.

``-buildarch x86_64``
    Set build architecture for the boot iso to x86_64.

``-s https://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/``
    Path corresponding to the main Fedora repository, used to get the package needed to build the minimal Linux distros for the boot iso.
    The repository must have an architecture corresponding to the one used for `--buildarch`.

``-s file:///rpms``
    Path to our repository folder with custom Anaconda packages situated in `/rpms`. The custom Anaconda RPMS will be preferred due to higher version.

``./output``
    Name of the output directory inside the Mock chroot. The directory must not exists or else Lorax will refuse to start the run.

In the last step we will pull the boot iso out from the Mock chroot:

::
    mock -r fedora-rawhide-x86_64 --copyout output/images/boot.iso .

The image will be stored into the `boot.iso` file in the current working directory.
