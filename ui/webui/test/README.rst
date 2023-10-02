Anaconda Web UI tests
=====================

The Web UI tests are based on cockpit's testing framework which in turn is based
on python's unittest library. There are two kinds of Web UI tests, "integration"
that test only one specific feature at a time and "end to end" that go through the
entire installation process including reboot to the installed system. Both types
use the same library of helper functions, to avoid duplicating code and to make
the test development easier, but they are executed in different ways because of
the higher requirements of the end to end tests.

Test development
----------------

Before test case for testing a new user interface can be written any new elements
in the UI that are going to be interacted with need to be covered by helper
functions. These helper functions are located in ``./ui/webui/test/helpers`` and
are organized by screens or installations steps. These helper functions are then
used in both integration and end to end tests.

For interaction with elements on page use class `Browser <https://github.com/cockpit-project/cockpit/blob/292/test/common/testlib.py#L182>`_.
For running commands in the installation environment use class `Machine <https://github.com/cockpit-project/bots/blob/1df595efa53fbf02731108d7a3657642d5b92c9e/machine/machine_core/machine.py#L55>`_ / `SSHConnection <https://github.com/cockpit-project/bots/blob/1df595efa53fbf02731108d7a3657642d5b92c9e/machine/machine_core/ssh_connection.py#L45>`_.

All helper functions should be decorated with `log_step <https://github.com/rhinstaller/anaconda/blob/anaconda-39.16-1/ui/webui/test/helpers/step_logger.py#L11>`_.
That makes sure the call and parameters are logged in the test output. The decorator
also has options to create browser snapshots (screenshot and html), currently enabled
only for end to end tests, and those should be used whenever the helper function is
interacting with the UI.

Web UI integration tests
========================

Integration tests are stored in directory `./ui/webui/test`, in files named `check-{something}`.

For information about the @nondestructive decorator and some best practices read `Cockpit's test documentation <https://github.com/cockpit-project/cockpit/tree/main/test/#nondestructive-tests>`_.
Before running the tests refer to the ``CONTRIBUTING`` guide in the root of the repository for installation of all the necessary build and test dependencies.

Preparation and general invocation
----------------------------------

*Warning*: Never run the build, test, or any other command here as root!

To run the WebUI tests run the following from the root of the anaconda repo.
(do NOT run the tests as root).

OSTree based systems (SilverBlue etc.) can use toolbx.
See `<../../../CONTRIBUTING.rst#setting-up-development-container>`_.

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

After the code is changed the testing environment needs to be updated.
The most robust way of doing this is::

    make create-updates.img

Interactive browser
-------------------

Normally each test starts its own chromium headless browser process on a
separate random port. To interactively follow what a test is doing::

    TEST_SHOW_BROWSER=1 test/check-basic --trace

You can also run a test against Firefox instead of Chromium::

    TEST_BROWSER=firefox test/check-basic --trace

See below for details.

Debug logging
-------------
Enable debug messages in an interactive browser in the JS console with:

.. code-block:: javascript

    window.debugging = "anaconda"

You can do that in a test as well, after the `Installer.open()` call:

.. code-block:: python

    self.brower.eval_js('window.debugging = "anaconda"')

This also supports other values, e.g. get verbose logging for `dbus` interactions. See
`Cockpit documentation <https://github.com/cockpit-project/cockpit/blob/main/HACKING.md#debug-logging-in-javascript-console>`_.

For debugging failures on CI without interactive access, it is helpful to
enable CDP and VM interaction logging as well:

.. code-block:: python

    self.browser.cdp.trace = True
    self.machine.verbose = True


Manual testing
--------------

You can conduct manual interactive testing against a test image by starting the
image like so::

    test/webui_testvm.py fedora-rawhide-boot

Once the machine is booted and the cockpit socket has been activated, a
message will be printed describing how to access the virtual machine, via
ssh and web.  See the "Helpful tips" section below.

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
        StrictHostKeyChecking=no
        UserKnownHostsFile=/dev/null

Cockpit's CI
------------

WebUI tests when running in CI they use Cockpit's infrastructure.
For information on the internals of Cockpit's CI see
`cockpituous documentation <https://github.com/cockpit-project/cockpituous/tree/main/tasks#readme>`_.

Web UI End to end tests
=======================

The end-to-end tests, along with tplib test cases and test plans (only required when
executing tests using Permian), are located in the ``./ui/webui/test/end2end`` directory.

End to end tests use one more level of abstraction, class `End2EndTest <https://github.com/rhinstaller/anaconda/blob/anaconda-39.16-1/ui/webui/test/helpers/end2end.py#L38>`_.
This class handles flow through all the required installation steps with default
options. So when writing new test you only have to use this class as parent and
extend it or reimplement the functions that are important for the test case.

End to end tests examples
--------------------------

There are three test cases in the anaconda repository that can be used as examples.

**Default**

Performs default installation.
Test script ``default.py``, test case file ``default.tc.yaml``.

**Storage encryption**

Makes changes, compared to default installation, only in the storage section of
the installation wizard and runs some commands before the system is rebooted.
Test script ``storage_encryption.py``, test case file ``storage_encryption.tc.yaml``.

**Wizard navigation**

Changes the way how the test steps through the installation wizard.
Test script ``wizard_navigation.py``, test case file ``wizard_navigation.tc.yam``.

Running End to end tests
-------------------------

The recommended way to run these tests is through a Permian workflow, which is explained
in detail in the documentation available `here <https://permian.readthedocs.io/en/devel/workflows/anaconda-webui.html>`_.
Alternatively, you can manually set up the environment and execute the tests individually.
Please refer to the `Preparation and general invocation`_ section for this.

For a comprehensive execution, including post-reboot checks, the tests need to be executed
on an existing machine where the installer is running with the cmdline options
``inst.sshd inst.webui.remote``. (VM spawned by cockpit framework won't survive reboot).
Here is an example that runs default test on VM with IP 192.168.122.235::

    WEBUI_TEST_DIR=./ui/webui/test ./ui/webui/test/end2end/default.py --machine 192.168.122.235:22 --browser 192.168.122.235:9090

If you run the tests on a machine created by the test script, they will timeout
when rebooting, but it can be still useful to use this workflow, eg. for local
testing during a test update or development::

    WEBUI_TEST_DIR=./ui/webui/test ./ui/webui/test/end2end/default.py DefaultInstallation.test_default_installation
