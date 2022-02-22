Anaconda Web UI
===============

Getting and building the source
-------------------------------

Make sure you have `npm` available (usually from your distribution package).
These commands check out the source and build it into the `dist/` directory::

    git clone https://github.com/rhinstaller/anaconda.git
    cd anaconda
    ./autogen.sh && ./configure
    cd ui/webui
    make

Note that this builds only the WebUI code. In most cases, the rest of Anaconda is needed too.

Running the UI interactively
----------------------------

First, build RPM packages in the CI container, from root of the repository::

    make -f ./Makefile.am anaconda-ci-build
    make -f ./Makefile.am container-shell
    ./autogen.sh && ./configure
    make rpms

Alternatively, you can install all the dependencies and build without using the container::

    sudo ./scripts/testing/install_dependencies.sh -y
    ./autogen.sh && ./configure
    make rpms

Note that if you went through this process already, you also need to remove the whole `ui/webui/bots/` directory before calling `make rpms`. Another pitfall is that the `bots` directory is a git repository and will not be removed with `git clean`.

Then, prepare the `~/.ssh/config` file according to instructions in `<test/README.rst>`_

Finally, set up the VM and start it::

    cd ui/webui
    make ../../updates.img
    mkdir -p test/images
    make bots
    ./bots/image-download fedora-rawhide-boot
    ./test/webui_testvm.py fedora-rawhide-boot

Once the machine is running, instructions for connecting to it will be printed.

Running eslint
--------------

Anaconda Web UI uses `ESLint <https://eslint.org/>`_ to automatically check
JavaScript code style in `.js` and `.jsx` files.

The linter is executed within every build as a webpack preloader.

For developer convenience, the ESLint can be started explicitly by::

    npm run eslint

Violations of some rules can be fixed automatically by::

    npm run eslint:fix

Rules configuration can be found in the `.eslintrc.json` file.

Development with rsync mode
---------------------------

When developing the Web UI, after every change to your sources the webpacks need to be rebuilt
and the contents of dist directory need to be copied to the SSH target's
/usr/share/cockpit/anaconda-webui directory.

For automating this, you need to set up the SSH `test-updates` alias,
as described in `<test/README.rst>`_.

Then you can run::

    make rsync
