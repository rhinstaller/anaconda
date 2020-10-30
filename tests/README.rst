Testing Anaconda
================

This document describes how to run Anaconda tests. Anaconda has various tests such as
unit tests, rpm tests and translation tests. All the tests will be run together if you follow
the steps below.

You have two possible ways how to run these tests:

- running the tests directly on your system
- using mock utility which run a container on your system

Read below about their benefits and drawbacks.

Run tests locally
-----------------

Before you are able to run Anaconda tests you need to install all required dependencies.
To get list of dependencies you can use::

    [dnf|yum] install -y $(./scripts/testing/dependency_solver.py)

Prepare the environment and build the sources::

    ./autogen.sh
    ./configure
    make

Executing the tests can be done with::

    make check

To run a single test do::

    make TESTS=install/nosetests.sh check

See `tests/Makefile.am` for possible values. Alternatively you can try::

    make ci

This has the advantage of producing Python test coverage for all tests.
In case the *ci* target fails there is also a *coverage-report* target
which can be used to combine the multiple `.coverage` files into one and
produce a human readable report.

Run tests inside of container
-----------------------------

Feel free to avoid installation of dependencies required for
`autogen.sh && ./configure` execution by replacing `make` calls below
with `make -f Makefile.am` in the Anaconda repository root directory.

Right now only unit tests are supported by the container, not rpm-tests.
Before being able to run the tests you have to build the container.
To build the container run::

    make anaconda-ci-build

Then you are free to run the tests without dependency installation by
running::

    make container-ci

This will run all the tests. To run just some tests you can pass parameters
which will replace the current one. For example to run just some nose-tests
please do this::

    make container-ci CI_CMD="make tests-nose-only NOSE_TESTS_ARGS=nosetests/pyanaconda_tests/kernel_test.py"

WARNING:

*Just one command* can be passed like this, if `&&` is used then only first
one is run in the container but everything else is started on host!

Logs from the run are stored in the ``test-logs/`` folder; no other files are
modified/touched by the container (it works on an internal copy of the host's
anaconda directory).

For interactively working in the container you can run::

    make container-shell

This command will open bash inside the container for you with mounted
current folder at the `/anaconda` path. This is a convenient way
how to run tests but avoid constant call of autotools and build during the
development.

Note:

Please update your container from time to time to have newest dependencies.
To do that just run the build again.

Tests in CI
-----------
The above container tests happen automatically on pull requests. As building
the RHEL 8 container needs to happen inside the Red Hat VPN, these run on
`self-hosted runners`_.

For debugging or development a self-hosted runner can be started in podman; see
the comment in github-action-run-once_ for details.

.. _`self-hosted runners`: https://docs.github.com/en/free-pro-team@latest/rest/reference/actions#self-hosted-runners
.. _github-action-run-once: ../dockerfile/anaconda-ci/github-action-run-once

Run tests inside Mock
---------------------

When using the `ci' target in a mock you need to use a regular user account which
is a member of the `mock' group. You can update your account by running
the command::

    # usermod -a -G mock <username>

To prepare testing mock environment call::

    ./scripts/testing/setup-mock-test-env.py [mock-configuration]

Mock configuration can be path to a file or name of file in `/etc/mock/*.cfg`
without suffix. For detail configuration look on the script help output.

Then you can run tests by::

    mock -r [mock_configuration] --chroot -- "cd /anaconda && ./autogen.sh && ./configure && make ci"

Or you can just attach to shell inside of the prepared mock environment::

    mock -r [mock_configuration] --shell

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
- *gui/* - specialized test suite for the graphical interface of anaconda. This
  is written in Python and uses the `dogtail <https://fedorahosted.org/dogtail/>`_
  accessibility module. All tests are executed using ./anaconda.py from the local
  directory;
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
