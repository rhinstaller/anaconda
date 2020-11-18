Testing Anaconda
================

This document describes how to run Anaconda tests. Anaconda has various tests
such as unit tests, rpm tests and translation tests.  All the tests will be run
together if you follow the steps below.  For integration tests there is a
separate repository kickstart-tests_ containing also tooling for running the tests.

Run tests inside of container
-----------------------------
This is the primary and recommended way to run the tests.

Right now only unit tests are supported by the container, not rpm-tests.
You can use our container image on `Quay.io <https://quay.io/repository/rhinstaller/anaconda-ci>`_
or you can build your own image.
(Optional) to build the container image run::

    make -f Makefile.am anaconda-ci-build

Then you are free to run the tests without dependency installation by
running::

    make -f Makefile.am container-ci

This will run all the tests, including Python test coverage reports. To run
just some tests you can pass parameters which will replace the current one. For
example to run just some nose-tests please do this::

    make -f Makefile.am container-ci CI_CMD="make tests-nose-only NOSE_TESTS_ARGS=nosetests/pyanaconda_tests/kernel_test.py"

WARNING:

*Just one command* can be passed like this, if `&&` is used then only first
one is run in the container but everything else is started on host!

Logs from the run are stored in the ``test-logs/`` folder; no other files are
modified/touched by the container (it works on an internal copy of the host's
anaconda directory).

Interactively work inside of container
--------------------------------------

For interactively working in the container you can run::

    make -f Makefile.am container-shell

This command will open bash inside the container for you with mounted
current folder at the `/anaconda` path. This is a convenient way
how to run tests but avoid constant call of autotools and build during the
development.

Prepare the environment and build the sources::

    ./autogen.sh
    ./configure
    make

Executing the tests can be done with::

    make check

To run a single test do::

    make TESTS=nosetests.sh check

See `tests/Makefile.am` for possible values. Alternatively you can try::

    make ci

This has the advantage of producing Python test coverage for all tests.
In case the *ci* target fails there is also a *coverage-report* target
which can be used to combine the multiple `.coverage` files into one and
produce a human readable report.

Note
----

Please update your container from time to time to have newest dependencies.
To do that, run `podman pull quay.io/rhinstaller/anaconda-ci:master` or build
it locally again.


Test Suite Architecture
------------------------

Anaconda has a complex test suite structure where each top-level directory
represents a different class of tests. They are

- *cppcheck/* - static C/C++ code analysis using the *cppcheck* tool;
- *dd_tests/* - Python unit tests for driver disk utilities (utils/dd);
- *dracut_tests/* - Python unit tests for the dracut hooks used to configure the
  installation environment and load Anaconda;
- *gettext/* - sanity tests of files used for translation; Written in Python and
  Bash;
- *glade/* - sanity tests for .glade files. Written in Python;
- *install/* - basic RPM sanity test. Checks if anaconda.rpm can be installed in
  a temporary directory without failing dependencies or other RPM issues;
- *lib/* - helper modules used during testing;
- *pyanaconda_tests/* - unit tests for the :mod:`pyanaconda` module;
- *pylint/* - checks the validity of Python source code using the *pocketlint*
  tool;
- *regex_tests/* - Python unit tests for regular expressions defined in
  :mod:`pyanaconda.regexes`;
- *storage/* - test cases used to verify partitioning scenarios for success or
  expected failures. The scenarios are described using kickstart snippets.
  Written in Python with a custom test case framework based on
  `blivet <https://github.com/storaged-project/blivet>`_;



.. NOTE::

    All Python unit tests inherit from the standard :class:`unittest.TestCase`
    class unless specified otherwise!

    Some tests require root privileges and will be skipped if running as regular
    user!

.. _kickstart-tests: https://github.com/rhinstaller/kickstart-tests
