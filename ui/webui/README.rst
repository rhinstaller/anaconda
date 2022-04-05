Anaconda Web UI
===============

Getting the source
-------------------------------

Here's where to get the code::

    git clone https://github.com/rhinstaller/anaconda.git
    cd anaconda

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
