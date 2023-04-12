Integration Tests of Anaconda WebUI
===================================

This directory contains automated integration tests for Anaconda WebUI, and the support files for them.

Before running the tests refer to the ``CONTRIBUTING`` guide in the root of the repository for installation of all the necessary build and test dependencies.

Preparation and general invocation
----------------------------------

*Warning*: Never run the build, test, or any other command here as root!

To run the WebUI integration tests run the following from the root of the anaconda repo.
(do NOT run the integration tests as root).

OSTree based systems (SilverBlue etc.) can use toolbx.
See `<../../../CONTRIBUTING.rst#how-to-run-make-commands>`_.

Then download test dependencies::

    cd ui/webui
    make prepare-test-deps

Prepare an updates.img containing the anaconda RPMs and the cockpit dependencies::

    make create-updates.img

Then download the ISO file that the test VMs will use::

    ./bots/image-download fedora-rawhide-boot

In most cases you want to run an individual test in a suite.
You also need to specify `TEST_OS` for each test run, for example::

   TEST_OS=fedora-rawhide-boot test/check-basic TestBasic.testNavigation

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

    TEST_OS=fedora-rawhide-boot test/common/run-tests --jobs 2

The tests will automatically download the VM isos they need, so expect
that the initial run may take a few minutes.

Updating the testing environment
--------------------------------

After the code is changed the testing environemnt needs to be updated.
The most robust way of doing this is (from top level directory)::

    rm -rf ui/webui/dist/ updates.img
    make rpms
    cd ui/webui
    make ../../updates.img

Interactive browser
-------------------

Normally each test starts its own chromium headless browser process on a
separate random port. To interactively follow what a test is doing::

    TEST_SHOW_BROWSER=1 test/check-basic --trace

You can also run a test against Firefox instead of Chromium::

    TEST_BROWSER=firefox test/check-basic --trace

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

For updating (pushing) updated pixel test reference images you can use the available the Makefile target::

    make update-reference-images

How to fix failed pixel tests
-----------------------------

For all the steps below you have to be in `ui/webui` directory of the project.

Locally just copy the broken tests images to the `test/reference` directory. However, easier
option to deal with this is to use automation which will download all the broken images from
fail test on PR::

    ./test/common/pixel-tests fetch <link to HTML with failed tests>

Example of such a call::

    ./test/common/pixel-tests fetch https://cockpit-logs.us-east-1.linodeobjects.com/pull-4551-20230322-101308-479c2fc1-fedora-rawhide-boot-rhinstaller-anaconda

The link will be link accessible from the `Details` button on GitHub PR with failed tests.

When the images are correctly updated just call to push the changes to pixel repository
(no review is required)::

    make update-reference-images

Then new commit is pushed to
["anaconda pixel tests repository"](https://github.com/rhinstaller/pixel-test-reference)
and just add reference git submodule to your existing PR by::

    git add test/reference
    git commit
    git push <your fork>

If everything went well your PR should be green now.

Outdated Cockpit CI image for testing
-------------------------------------

From time to time you can face an issue that the fedora-X-boot image on Cockpit side is
missig dependency for your PR. **You should not push your PR without fixing the image first!**

To update the image please ping #cockpit on IRC and they will provide a PR with the new image.
It will look similar to ["this"](https://github.com/cockpit-project/bots/pull/4551).

Then you can test your Anaconda PR against this new builded image on cockpit PR by::

    ./bots/tests-trigger --bots-pr <PR number on cockpit repo> <your Anaconda PR number> <image-name>

Example of such a call could be::

    ./bots/tests-trigger --bots-pr 4551 4634 fedora-rawhide-boot
    ./bots/tests-trigger --bots-pr 4551 4634 fedora-38-boot

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

    TEST_AUDIT_NO_SELINUX  Ignore unexpected journal messages related to selinux audit.
                           Can be useful when running tests locally.

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
