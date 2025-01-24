Testing Anaconda
================

This document describes how to run Anaconda tests. Anaconda has various tests
such as unit tests, rpm tests and translation tests.  All the tests will be run
together if you follow the steps below.  For integration tests there is a
separate repository kickstart-tests_ containing also tooling for running the tests.

Testing in containers
---------------------

Most of our current testing is set inside the containers. This section will describe
how to correctly run and build these containers.

Run unit tests inside of container
__________________________________
This is the primary and recommended way to run the tests.

Right now only unit tests are supported by the container, not rpm-tests.
You can use our container image on `quay.io`_
or you can build your own image.
(Optional) to build the container image run::

    make -f Makefile.am anaconda-ci-build

Then you are free to run the tests without dependency installation by
running::

    make -f Makefile.am container-ci

This will run all the tests, including Python test coverage reports. To run
just some tests you can pass parameters which will replace the current one. For
example to run just some unit tests please do this::

    make -f Makefile.am container-ci CI_CMD="make tests-unit-only UNIT_TESTS_PATTERN='test_layout_variant_'"

The ``UNIT_TESTS_PATTERN`` variable is passed to `pytest -k`_. See
the documentation for more info.

To run a different kind of test than unit tests, do this::

    make -f Makefile.am container-ci CI_CMD="make check TESTS='cppcheck/runcppcheck.sh'"

WARNING:

*Just one command* can be passed like this, if `&&` is used then only first
one is run in the container but everything else is started on host!

Logs from the run are stored in the ``test-logs/`` folder; no other files are
modified/touched by the container (it works on an internal copy of the host's
anaconda directory).

Interactively work inside of container
______________________________________

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

For RHEL 10 use this instead (glade needs to be disabled at build time)::

    ./autogen.sh
    ./configure --disable-glade
    make

Executing the tests can be done with::

    make check

To run a single test do::

    make TESTS=unit_tests/unit_tests.sh check


To run a subset of unit tests do::

    make TESTS=unit_tests/unit_tests.sh UNIT_TESTS_PATTERN='test_layout_variant_' check

The ``UNIT_TESTS_PATTERN`` variable is passed to `pytest -k`_. See
the documentation for more info.

See `tests/Makefile.am` for possible values. Alternatively you can try::

    make ci

This has the advantage of producing Python test coverage for all tests.
In case the *ci* target fails there is also a *coverage-report* target
which can be used to combine the multiple `.coverage` files into one and
produce a human readable report.

Run rpm tests inside of container
_________________________________

The rpm tests are taking care that rpm file has all necessary content.

To run the test in a container::

    make -f Makefile.am container-rpm-test

Run unit tests with patched pykickstart or other libraries
__________________________________________________________

1. Pull the container::

      podman pull quay.io/rhinstaller/anaconda-ci:main

2. Run the container temporary with your required resources (pykickstart in this example)::

      podman run --name=cnt-add --rm -it -v ./pykickstart:/pykickstart:z quay.io/rhinstaller/anaconda-ci:main sh

3. Do your required changes in the container (install pykickstart in this example)::

      cd /pykickstart && make install DESTDIR=/

4. Commit the changed container as updated one. **DO NOT exit the running container, run this command in new terminal!**

      podman commit cnt-add quay.io/rhinstaller/anaconda-ci:main

   You can change the ``main`` tag to something else if you don't want to replace the existing one.
   Feel free to exit the running container now.

5. Run other commands for container ci as usual. Don't forget to append ``CI_TAG=<your-tag>`` to
   make calls if you committed the container under a custom tag.

Keep your containers updated
____________________________

Please update your container from time to time to have newest dependencies.
To do that, run::

    podman pull quay.io/rhinstaller/anaconda-ci:main

or build it locally again by::

    make -f ./Makefile.am anaconda-ci-build


GitHub workflows
----------------

All test and maintenance actions are run by `GitHub workflows`_.  These YAML
files completely describe what steps are required to run some action, what are
its triggers and so on.

Because we are using self-hosted runners, ``pull_request_trigger`` and other reasons,
we have our GitHub repositories configured that they need approval for every execution
of the tests (including after force push) for every external contributors.

Pull request for main:
________________________

Unit and rpm tests are using the GitHub `pull_request` trigger.  We use GitHub's
runners for this so we don't have to care about what is executed there.

The test workflow rebuilds the ``anaconda-ci`` container if the container files
have changed, otherwise it is pulling the container from `quay.io`_. For more
information see below.

Pull request for RHEL:
______________________

Unit and rpm tests are using a similar solution as the upstream ones. Containers
are build on top of ``quay.io/centos/centos:streamXX`` images where ``XX`` is RHEL major release
number. Code for RHEL is shared with CentOS Stream so we decided to run tests on
CentOS Stream containers as these are easier to integrate.

Running kickstart-tests:
________________________

The `kickstart-tests.yml workflow`_ allows rhinstaller organization members to
run kickstart-tests_ against an anaconda PR (only ``main`` for now). Send a
comment that starts with ``/kickstart-tests <options>`` to the pull request to
trigger it. It is possible to use tests updated via a kickstart-tests
repository PR. See the `kickstart-tests.yml workflow`_ for supported
options. For more detailed information on tests selection see the
`kickstart launch script`_ documentation and-its ``--help``.

Container maintenance
---------------------

All active branches run tests in containers. Containers have all the
dependencies installed and the environment prepared to run tests or connect our
GitHub runners (for places where we need /dev/kvm access).

Automatic container build
_________________________

Containers are updated daily by the `container-autoupdate.yml workflow`_
from Anaconda ``main`` repository. Before pushing a new
container, tests are executed on this container to avoid regressions.

Manual container build
______________________

Just go to the `actions tab`_ in the Anaconda repository to the
“Refresh container images“ and press the ``Run workflow`` button on a button on
a particular branch. Usually ``main``, but for testing a change to the
container you can push your branch to the origin repo and run it from there.

Security precautions for testing RHEL
-------------------------------------

Beware of the ``pull_request_target``
_____________________________________

For many reasons, we are using ``pull_request_trigger`` in our workflows, however,
this trigger is not secure in some scenarios. See `GitHub documentation`_ for more
information. We need to make sure that this trigger is not executed on an unsafe code.

The main issue starts with running these on checkout code from PR. In this case,
the attacker has a free hand to change our code, do a release, or use our
self-hosted runners.

As the first line of defense, we are not running automatically any workflows on
a pull request from external contributors and each test run have to be manually
approved by developer.

How can I change the workflow
_____________________________

It depends on a `GitHub trigger`_ used by the workflow. However, if it is not
possible to create a PR and see your changes, you can create PR on your fork
branch which has the updated workflow. I would recommend you to create a test
organization for this and avoid creating a new account.

Similar situation works even for workflow to automatically update our containers.
This workflow has ``schedule`` and ``manual_dispatch`` triggers. ``schedule``
triggers are always run on the default branch. For testing updates, always add
``manual_dispatch`` so that you can run them from your branch (on either origin
or your fork).


Test Suite Architecture
------------------------

Anaconda has a complex test suite structure where each top-level directory
represents a different class of tests. They are

- *cppcheck/* - static C/C++ code analysis using the *cppcheck* tool;
- *shellcheck/* - shell code analyzer config;
  installation environment and load Anaconda;
- *gettext/* - sanity tests of files used for translation; Written in Python and
  Bash;
- *glade_tests/* - sanity tests for .glade files. Written in Python;
- *rpm_tests/* - basic RPM sanity test. Checks if anaconda.rpm can be installed in
  a temporary directory without failing dependencies or other RPM issues and checks if
  all files are correctly present in the RPM;
- *lib/* - helper modules used during testing;
- *unit_tests/dd_tests/* - Python unit tests for driver disk utilities (dracut/dd);
- *unit_tests/dracut_tests/* - Python unit tests for the dracut hooks used to configure the
- *unit_tests/pyanaconda_tests/* - unit tests for the :mod:`pyanaconda` module;
- *unit_tests/regex_tests/* - Python unit tests for regular expressions defined in
- *unit_tests/shell_tests/* - Python unit tests for the shell code in Dracut
- *pylint/* - checks the validity of Python source code
  tool;
- *ruff/* - config for fast but not 100% correct linter for Python;
- *vulture/* - scripts to execute vulture linter used to find a dead code in the project
  :mod:`pyanaconda.regexes`;

.. NOTE::

    All Python unit tests inherit from the standard :class:`unittest.TestCase`
    class unless specified otherwise!

    Also tests are written in the Python `unittests library`_ style but they are executed
    by `pytest`_.

    Some tests require root privileges and will be skipped if running as regular
    user!

The `cppcheck` test is optional and is automatically skipped if the package is not available.

The tests use the `automake "simple tests" framework <https://www.gnu.org/software/automake/manual/automake.html#Simple-Tests>`.
The launcher scripts are listed under `TESTS` in `tests/Makefile.am`.

.. _kickstart-tests: https://github.com/rhinstaller/kickstart-tests
.. _quay.io: https://quay.io/repository/rhinstaller/anaconda-ci
.. _pytest -k: https://docs.pytest.org/en/7.1.x/reference/reference.html#command-line-flags
.. _GitHub workflows: https://docs.github.com/en/free-pro-team@latest/actions
.. _kickstart-tests.yml workflow: ../.github/workflows/kickstart-tests.yml
.. _kickstart launch script: https://github.com/rhinstaller/kickstart-tests/blob/master/containers/runner/README.md
.. _container-autoupdate.yml workflow: ../.github/workflows/container-autoupdate.yml
.. _actions tab: https://github.com/rhinstaller/anaconda/actions?query=workflow%3A%22Refresh+container+images%22
.. _unittests library: https://docs.python.org/3/library/unittest.html
.. _pytest: https://docs.pytest.org/en/stable/
.. _GitHub documentation: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#pull_request_target
.. _GitHub trigger: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows
