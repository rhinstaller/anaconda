Integration Tests of Anaconda WebUI
===================================

This directory contains automated integration tests for Anaconda WebUI, and the support files for them.

Before running the tests refer to the ``CONTRIBUTING`` guide in the root of the repository for installation of all the necessary build and test dependencies.

Preparation and general invocation
----------------------------------

*Warning*: Never run the build, test, or any other command here as root!

To run the WebUI integration tests run the following from the root of the anaconda repo.
(do NOT run the integration tests as root)::

You first need to build anaconda RPMS::

    make rpms

Then prepare an updates.img containing the anaconda RPMs and the cockpit dependencies::

    cd ui/webui && make ../../updates.img

In most cases you want to run an individual test in a suite, for example::

   test/check-basic TestBasic.testHelp

You can get a list of tests by inspecting the `def test*` in the source, or by
running the suite with `-l`/`--list`::

    test/check-basic -l

Sometimes you may also want to run all tests in a test file suite::

    test/check-basic

To see more verbose output from the test, use the `-v`/`--verbose` and/or `-t`/`--trace` flags::

    test/check-basic --verbose --trace

If you specify `-s`/`--sit` in addition, then the test will wait on failure and
allow you to log into cockpit and/or the test instance and diagnose the issue.
The cockpit and SSH addresses of the test instance will be printed::

    test/check-basic -st

You can also run *all* the tests, with some parallelism::

    test/run-tests --jobs 2

The tests will automatically download the VM isos they need, so expect
that the initial run may take a few minutes.

Interactive browser
-------------------

Normally each test starts its own chromium headless browser process on a
separate random port. To interactively follow what a test is doing::

    TEST_SHOW_BROWSER=1 test/check-basic--trace

You can also run a test against Firefox instead of Chromium::

    TEST_BROWSER=firefox test/check-basic--trace

See below for details.


Manual testing
--------------

You can conduct manual interactive testing against a test image by starting the
image like so::

    webui_testvm.py fedora-rawhide-boot

Once the machine is booted and the cockpit socket has been activated, a
message will be printed describing how to access the virtual machine, via
ssh and web.  See the "Helpful tips" section below.


Guidelines for writing tests
----------------------------

For information about the @nondestructive decorator and some best practices read `Cockpit's test documentation <https://github.com/cockpit-project/cockpit/tree/main/test/#guidelines-for-writing-tests>`_.

Running tests against existing machines
---------------------------------------

Once you have a test machine that contains the version of Anaconda that you want
to test, you can run tests by picking a program and just executing it against the running machine::

    test/check-basic --machine=127.0.0.2:22000 --browser 127.0.0.2:9091

Pixel tests
-----------

The verify test suite contains ["pixel tests"](https://cockpit-project.org/blog/pixel-testing.html).
Make sure to create the test/reference submodule before running tests which contain pixel tests.::

    make test/reference

For information on how to debug, update or review pixel tests reference the
["pixel tests"](https://cockpit-project.org/blog/pixel-testing.html) documentation.
Make sure to set::

    GITHUB_BASE=rhinstaller/anaconda

before running any commands suggested there. For updating pixel test reference images you can use
the available the Makefile target::

    make update-test-reference


Test Configuration
------------------

You can set these environment variables to configure the test suite::

    TEST_OS    The OS to run the tests in.  Currently supported values:
                  "fedora-rawhide-boot"

    TEST_BROWSER  What browser should be used for testing. Currently supported values:
                     "chromium"
                     "firefox"
                  "chromium" is the default.

    TEST_SHOW_BROWSER  Set to run browser interactively. When not specified,
                       browser is run in headless mode.

Debugging tests
---------------

If you pass the `-s` ("sit on failure") option to a test program, it
will pause when a failure occurs so that you can log into the test
machine and investigate the problem.

A test will print out the commands to access it when it fails in this
way. You can log into a running test-machine using ssh.

You can also put calls to `sit()` into the tests themselves to stop them
at strategic places.

That way, you can run a test cleanly while still being able to make
quick changes, such as adding debugging output to JavaScript.

Helpful tips
------------

If you add a snippet like this to your `~/.ssh/config` then you'll be able to
connect to the test VMs by typing `ssh test-updates`::

    Host test-updates
        Hostname 127.0.0.2
        Port 2201
        User root

Cockpit's CI
------------

WebUI tests when running in CI they use Cockpit's infrastructure.
For information on the internals of Cockpit's CI see
`cockpituous documentation <https://github.com/cockpit-project/cockpituous/tree/main/tasks#readme>`_.


Running tests in a toolbox
--------------------------

Cockpit's CI container can be used for local development with
`toolbox <https://github.com/containers/toolbox>`_, to get an "official"
development environment that's independent from the host::

    toolbox create --image quay.io/cockpit/tasks -c cockpit
    toolbox enter cockpit
