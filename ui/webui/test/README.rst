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

Alternatively, you can conduct manual testing against a test VM by starting the test VM like this::

    RPM_PATH=/path/to/anaconda/repo/result/build/01-rpm-build/ make vm-run

Note that it's necessary to set the RPM_PATH variable pointing to the directory where the RPM files are.

Once the machine is running you can connect to it as follows::

    ssh -p 22000 root@127.0.0.2

Running tests against existing machines
---------------------------------------

Once you have a test machine that contains the version of Anaconda that you want
to test, you can run tests by picking a program and just executing it against the running machine::

    TEST_ALLOW_NOLOGIN=true test/check-basic --machine=127.0.0.2:22000 --browser 127.0.0.2:9091

Test Configuration
------------------

You can set these environment variables to configure the test suite::

    TEST_ALLOW_NOLOGIN  This option must be always set.
                        In the anaconda environment /run/nologin always exists
                        however cockpit test suite expects it to not exist

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
        Port 22000
        User root
