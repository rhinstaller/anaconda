Integration Tests of Anaconda WebUI
===================================

This directory contains automated integration tests for Anaconda WebUI, and the support files for them.

Introduction
------------

Before running the tests refer to the ``CONTRIBUTING`` guide in the root of the repository for installation of all the necessary build and test dependencies.

To run the WebUI integration tests run the following from the root of the anaconda repo.
(do NOT run the integration tests as root)::

    make webui-tests

The tests will automatically download the latest rawhide boot.iso they need, so expect that the initial run may take a couple of minutes.


Manual testing
--------------

You can conduct manual interactive testing against a test image by starting the
image like so::

    webui_testvm.py fedora-rawhide

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

Test Configuration
------------------

You can set these environment variables to configure the test suite::

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
