Testing Anaconda
================

Testing locally
---------------

Before testing Anaconda you need to install all required dependencies.
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

.. NOTE::

    Your regular user account also needs to execute `sudo' because some tests
    require root privileges!

Testing Inside Mock
-------------------

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
  `blivet <https://github.com/rhinstaller/blivet>`_;



.. NOTE::

    All Python unit tests inherit from the standard :class:`unittest.TestCase`
    class unless specified otherwise!

    Some tests require root privileges and will be skipped if running as regular
    user!

