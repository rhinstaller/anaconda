Contribution guidelines
=======================

This guide describes rules for how to get your contributions into Anaconda. However, if you seek
help with implementing changes in Anaconda, please follow our
`blog series <https://rhinstaller.wordpress.com/2019/10/11/anaconda-debugging-and-testing-part-1/>`_ or
an `addon guide <http://rhinstaller.github.io/anaconda-addon-development-guide/index.html>`_ to create Anaconda addon.

Setting up development container
--------------------------------

The anaconda team uses a containerized development environment using toolbx.
If you can install [toolbx](https://containertoolbx.org/) or
[distrobox](https://distrobox.privatedns.org/) on your system, it is highly
recommended to do that:

 - It is known to work and gives you reproducible results.
 - It avoids having to install development packages on your main machine.

If you are not interested in dealing with containers, just skip this part and continue on the next one::

    sudo dnf install toolbox

To create and enter a development toolbx for Anaconda (not Web UI) just run these commands::

    toolbox create
    toolbox enter

To create and enter a development toolbx for Anaconda Web UI run this command instead::

    toolbox create --image quay.io/cockpit/tasks -c anaconda-webui
    toolbox enter anaconda-webui

Installing dependencies
-----------------------

If you are using [cockpit/tasks container](https://quay.io/repository/cockpit/tasks)
for Web UI development only, you can skip this part.

To get all the dependencies and prepare the environment in the container or
on your system just run these commands::

    sudo ./scripts/testing/install_dependencies.sh

For testing also the Web UI, you need to install additional dependencies::

    sudo ./scripts/testing/install_webui_dependencies.sh


How to run make commands
------------------------

Anaconda uses autotools so there are familiar `./configure` script and  Makefile targets.
To prepare Anaconda sources, you need to run these commands::

    ./autogen.sh && ./configure

How to Contribute to the Anaconda Installer (the short version)
----------------------------------------------------------------

1) I want to contribute to the upstream Anaconda Installer (used in Fedora):

- base and test your changes on a clone of the ``fedora-<next Fedora number>`` branch.
- open a pull request for the ``fedora-<next Fedora number>`` branch (``fedora-38``, etc.)
- check the *Commit Messages* section below for how to format your commit messages
- check the *Release Notes* section below for how to provide a release note

2) I want to contribute to the RHEL Anaconda installer:

- base and test your changes on a clone of the ``rhel-<RHEL number>``  branch.
- open a pull request for the ``rhel-<RHEL number>``  branch (``rhel-9``, etc.)
- check the *Commits for RHEL Branches* section below for how to format your commit messages
- check the *Release Notes* section below for how to provide a release note

If you want to contribute a change to both the upstream and RHEL Anaconda then follow both 1) and 2) separately.

Which is my target git branch?
------------------------------

Depending on where you want to make your contribution please choose your correct branch based on the table below.

+--------------------------+--------------+
| Fedora Rawhide           | master       |
+--------------------------+--------------+
| Fedora XX                | fedora-XX    |
+--------------------------+--------------+
| RHEL-X / CentOS Stream X | rhel-X       |
+--------------------------+--------------+

All of these branches are independent, never merged into each another, so if you want to put your
changes into multiple branches, you have to open multiple pull requests.

Finding Bugs to Fix
-------------------

The development team can mark bugs with specific keywords to show that they belong to a specific
category. You can quickly list these by searching the Red Hat bugzilla for bugs in the
``anaconda`` component with specific keywords in Whiteboard:

- For good first issues and simple fixes, the keyword is `EasyFix <https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&classification=Fedora&component=anaconda&f1=status_whiteboard&list_id=11496717&o1=substring&product=Fedora&query_format=advanced&v1=EasyFix>`_.

- For Btrfs-related issues, use keyword `Btrfs <https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&classification=Fedora&component=anaconda&f1=status_whiteboard&list_id=11496717&o1=substring&product=Fedora&query_format=advanced&v1=Btrfs>`_.

- For issues that are good candidates for `pure community features <pure-community-features>`_, search for `CommunityFeature <https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&classification=Fedora&component=anaconda&f1=status_whiteboard&list_id=11496717&o1=substring&product=Fedora&query_format=advanced&v1=CommunityFeature>`_.

(A single issue could potentially have more than one of these keywords.)

Patches for bugs without keywords are welcome, too!

WebUI development
-----------------

For good starting points how to develop and test Web UI interface of Anaconda see ``ui/webui/README.rst`` and ``ui/webui/test/README.rst``.

PatternFly
^^^^^^^^^^

Provides all the Web UI Widgets we use.

https://www.patternfly.org/v4/

NOTE: Right now we are using PatternFly 4 & version 5 is about to be released. Please take this into account when referencing the documentation.

Pixel tests
^^^^^^^^^^^

Make it possible to watch for unintended graphical changes as well as verifying that automated NPM dependency updates have not caused any visible breakage.

At a glance - on the Cockpit blog:

https://cockpit-project.org/blog/pixel-testing.html

Cockpit test framework
^^^^^^^^^^^^^^^^^^^^^^

An easy to use Python test framework, that makes it possible to test the Web UI. All our Web UI unit tests use this framework.

https://github.com/cockpit-project/cockpit/tree/main/test

There is a some documentation about how to use this framework from the Cockpit PoV, which still can be a useful reference for the various available options:

https://cockpit-project.org/external/source/test/README

Our cockpit test framework based tests for the Anaconda Web UI are located here:

https://github.com/rhinstaller/anaconda/tree/master/ui/webui/test

Do note that we try to de-duplicate often used testing functionality in a library, located in the ``helpers`` directory.

Cockpit CI infrastructure
^^^^^^^^^^^^^^^^^^^^^^^^^

Web UI pull request tests run on Cockpit CI infrastructure.

https://github.com/cockpit-project/cockpituous/tree/main/tasks#github-webhook-integration

Basically all the tests that run in Cockpit infra can be run locally, which can be very handy development and to debug CI issues.

Build Web UI boot.iso from a pull request
-----------------------------------------

We have a workflow setup to build boot.iso images that boot into the Anaconda Web UI from arbitrary pull requests.

To trigger a Web UI boot iso build, go to a pull request page and post a comment like this:

    /boot-iso --webui

This will trigger an automated Web UI boot iso build - you can check its progress via the "boot-iso" status among the status listing for the PR.

Once the workflow finishes running, checkout the "boot-iso" status again & look for a big zip file in the "artifacts" section - it will contain the resulting boot.iso corresponding to the PR.

Debugging Anaconda Web UI on the Live image
-------------------------------------------

The way Anaconda is currently setup, once the ``anaconda-webui`` package is installed, the Web UI will be started instead of the GTK GUI.

This is very useful, as it makes it possible to easily test Web UI changes on Live images (both regular & Live images built with ``anaconda-webui`` already installed) by just installing RPMS corresponding to the Anaconda code one wants to test.

The first step is to on the Live image (presumably running on a network reachable VM or machine) set password for the default user account & start sshd:

    sudo passwd liveuser
    sudo systemctl start sshd

Also check the IP of the machine:

    ip a

Then on your machine from your anaconda checkout, build the Anaconda RPMs:

    make -f Makefile.am container-rpms

Once the build finishes, enter the results directory and copy the RPMs to the Live image environment:

    cd result/build/01-rpm-build/
    scp *.rpm liveuser@<Live machine IP>:/tmp

Back on the Live media, install the new Anaconda RPMs:

    cd /tmp
    sudo dnf install *.rpm

After this, the Anaconda Web UI should be started when you launch the liveinst script:

    liveinst

Or when you click the "install to hard drive" icon.

It should be possible to do the whole build-scp-install-run multiple times on a single Live image boot.

Just take into account that the system Journal will contain log messages from all the installation runs, which could be confusing.

If you want to revert back to the GTK UI for some reason, just uininstall the ``anaconda-webui`` package.

Testing Anaconda changes
------------------------

To test changes in Anaconda you have a few options based on what you need to do.

Backend and TUI development
^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are two options to develop and test changes which are not yet released.

To find out more information about quick way to propagate your changes into the existing installation ISO image see `this blogpost <https://rhinstaller.wordpress.com/2019/10/11/anaconda-debugging-and-testing-part-1/>`_.

Another way is to build the boot.iso directly (takes more time but it's easier to do).

Build Anaconda RPM files with our container::

  make -f ./Makefile.am container-rpms-scratch

Then build ISO from these RPMs by this call (beware because of loop device mounting it needs root priviledges)::

  make -f ./Makefile.am container-iso-build

or for Web UI image run::

  make -f ./Makefile.am container-webui-iso-build

The resulting ISO will be stored in ``./result/iso`` directory.


Anaconda Installer Branching Policy (the long version)
-------------------------------------------------------

The basic premise is that there are the following branches:

- master
- fedora-<next fedora number>

The ``master`` branch never waits for any release-related processes to take place and is used for Fedora Rawhide Anaconda builds.

Concerning current RHEL branches, they are too divergent to integrate into this scheme. Thus, commits are merged onto, and builds are done on the RHEL branches.
In this case, multiple pull requests will very likely be needed:

- one for the ``rhel<number>-branch``
- one for the ``master`` branch, if the change is not RHEL only
- one for the ``fedora-<number>`` branch, if change should apply to branched Fedora too

Releases
---------

The release process is as follows, for both Fedora Rawhide and branched Fedora versions:

- a release commit is made (which bumps version in spec file) & tagged on the ``fedora-XX`` or ``master`` branch

Concerning the ``<next Fedora number>`` branches (which could also be called ``next stable release`` if we wanted to decouple our versioning from Fedora in the future):

- work which goes into the next Fedora goes to ``fedora-<next Fedora number>`` and must have another PR for ``master``, too
- stuff we *don't* want to go to the next Fedora (too cutting edge, etc.) goes only to ``master`` branch
- commits specific to a given Fedora release (temporary fixes, etc.) go only to the ``fedora-<next Fedora number>`` branch
- this way we can easily see what was developed in which Fedora timeframe and possibly due to given Fedora testing phase feedback (bugfixes, etc.)

Example for the F38 and F39 cycle
----------------------------------

Once Fedora 38 is branched, we have these branches in the repository:

- ``master``
- ``fedora-38``

This would continue until f38 is released, after which we:

- keep the ``fedora-38`` branch as an inactive record of the f38 cycle
- work on the ``master`` branch only

After a while, Fedora 39 is branched and we start the ``fedora-39`` branch off the ``master`` branch.

This will result in the following branches for the f39 cycle:

- ``master``
- ``fedora-39``

Guidelines for Commits
-----------------------

Commit Messages
^^^^^^^^^^^^^^^^

The first line should be a succinct description of what the commit does, starting with capital and ending without a period ('.'). If your commit is fixing a bug in Red Hat's bugzilla instance, you should add ``(#123456)`` to the end of the first line of the commit message. The next line should be blank, followed (optionally) by a more in-depth description of your changes. Here's an example:

    Stop kickstart when space check fails

    Text mode kickstart behavior was inconsistent, it would allow an
    installation to continue even though the space check failed. Every other
    install method stops, letting the user add more space before continuing.

Commits for RHEL Branches
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are submitting a patch for any rhel-branch, the last line of your commit must identify the bugzilla bug id it fixes, using the ``Resolves`` or ``Related`` keyword, e.g.:
``Resolves: rhbz#111111``

or

``Related: rhbz#1234567``

Use ``Resolves`` if the patch fixes the core issue which caused the bug.
Use ``Related`` if the patch fixes an ancillary issue that is related to, but might not actually fix the bug.

Release Notes
^^^^^^^^^^^^^

If you are submitting a patch that should be documented in the release notes, create a copy of the
``docs/release-notes/template.rst`` file, modify its content and add the new file to your patch, so
it can be reviewed and merged together with your changes.

After a final release (for example, Fedora GA), we will remove all release notes from
``docs/release-notes/`` of the release branch and add the content into the ``docs/release-notes.rst``
file.

This change will be ported to upstream to remove the already documented release notes from
``docs/release-notes/`` of the upstream branch. In a case of RHEL, port only the new release file.

Pull Request Review
^^^^^^^^^^^^^^^^^^^^

Please note that there is a minimum review period of 24 hours for any patch. The purpose of this rule is to ensure that all interested parties have an opportunity to review every patch. When posting a patch before or after a holiday break it is important to extend this period as appropriate.

All subsequent changes made to patches must be force-pushed to the PR branch before merging it into the main branch.

Code conventions
----------------

It is important to have consistency across the codebase. This won't necessarily make your code work better, but it might help to make the codebase more understandable, easier to work with, and more pleasant to go through when doing a code review.

In general we are trying to be as close as possible to `PEP8 <https://www.python.org/dev/peps/pep-0008/>`_ but also extending or modifying minor PEP8 rules when it seems suitable in the context of our project. See list of the conventions below:

* Limit all lines to a maximum of 99 characters.
* Format strings with `.format() <https://docs.python.org/3/library/stdtypes.html#str.format>`_ instead of ``%`` (https://pyformat.info/)
    * Exception: Use ``%`` formatting in logging functions and pass the ``%`` as arguments. See `logging format interpolation <https://stackoverflow.com/questions/34619790/pylint-message-logging-format-interpolation>`_ for the reasons.
* Follow docstring conventions. See `PEP257 <https://www.python.org/dev/peps/pep-0257>`_.
* Use `Enum <https://docs.python.org/3/library/enum.html>`_ instead of constants is recommended.
* Use ``super()`` instead of ``super(ParentClass, self)``.
* Use only absolute imports (instead of relative ones).
* Use ``ParentClass.method(self)`` only in case of multiple inheritance.
* Instance variables are preferred, class variables should be used only with a good reason.
* Global instances and singletons should be used only with a good reason.
* Never do wildcard (``from foo import *``) imports with the exception when all Anaconda developers agree on that.
* Use ``raise`` & ``return`` in the doc string. Do not use ``raises`` or ``returns``.
* Methods that return a task should have the suffix ‘_with_task’ (for example discover_with_task and DiscoverWithTask).
* Prefer to use ``pyanaconda.util.join_paths`` over ``os.path.join``. See documentation for more info.
* Never call ``upper()`` on translated strings. See the bug `1619530 <https://bugzilla.redhat.com/show_bug.cgi?id=1619530>`_
* Names of signal handlers defined in ``.glade`` files should have the ``on_`` prefix.

Merging examples
----------------

Merging a GitHub pull request
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(Fedora 38 is used as an example, don't forget to use appropriate Fedora version.)

Press the green *Merge pull request* button on the pull request page.

Then you are done.

Merging a topic branch manually
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(Fedora 38 is used as an example, don't forget to use appropriate Fedora version.)

Let's say that there is a topic branch called "fix_foo_with_bar" that should be merged to a given Anaconda non-topic branch.

Checkout the given target branch, pull it and merge your topic branch into it::

    git checkout <target branch>
    git pull
    git merge --no-ff fix_foo_with_bar

Then push the merge to the remote::

    git push origin <target branch>

If the pull request has been opened for the ``fedora-38`` branch, then you also need to check if the same change should go to the ``master`` branch in anoter PR.

.. _pure-community-features:

Pure community features
-----------------------

The pure community features are features which are part of the Anaconda code base but they are maintained and extended mainly by the community. These features are not a priority for the Anaconda project.

In case of issues in pure community features, the Anaconda team will provide only sanity checking. It is the responsibility of the community (maintainers of the feature) to provide fix for the issue. If the issue will have bigger impact on other parts of the Anaconda project or if it will block a release or another priority feature and the fix won't be provided in a reasonable time the Anaconda team reserves the rights to remove or disable this feature from the Anaconda code base.

Below is a list of pure community features, their community maintainers, and maintainers contact information:

/boot on btrfs subvolume
^^^^^^^^^^^^^^^^^^^^^^^^

* Origin: https://github.com/rhinstaller/anaconda/pull/2255
* Bugzilla: https://bugzilla.redhat.com/show_bug.cgi?id=1418336
* Maintainer: Neal Gompa <ngompa13@gmail.com>
* Description:

``Enable boot of the installed system from a BTRFS subvolume.``

systemd-boot as a bootloader
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Origin: https://github.com/rhinstaller/anaconda/pull/4368
* Bugzilla: https://bugzilla.redhat.com/show_bug.cgi?id=2135531
* Maintainer: Jeremy Linton <jeremy.linton@arm.com>
* Description:

``Enable boot using systemd-boot rather than grub2.``
