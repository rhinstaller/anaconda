Contribution guidelines
=======================

This guide describes rules for how to get your contributions into Anaconda. However, if you seek
help with implementing changes in Anaconda, please follow our
`blog series <https://rhinstaller.wordpress.com/2019/10/11/anaconda-debugging-and-testing-part-1/>`_ or
an `addon guide <http://rhinstaller.github.io/anaconda-addon-development-guide/index.html>`_ to create Anaconda addon.

How to Contribute to the Anaconda Installer (the short version)
----------------------------------------------------------------

a) I want to contribute to the upstream Anaconda Installer (used in Fedora):

- open a pull request for the ``<next Fedora number>-devel`` branch (f25-devel, etc.)
- check the *Commit Messages* section below for how to format your commit messages

b) I want to contribute to the RHEL Anaconda installer:

- open a pull request for the ``<RHEL number>-branch``  branch (rhel7-branch, etc.)
- check the *Commits for RHEL Branches* section below for how to format your commit messages

If you want to contribute a change to both the upstream and RHEL Anaconda then follow both a) and b) separately.

Anaconda Installer Branching Policy (the long version)
-------------------------------------------------------

The basic premise is that there are the following branches:

- master
- <next fedora number>-release
- <next fedora number>-devel

``Master`` branch never waits for any release-related processes to take place and is used for Fedora Rawhide Anaconda builds.

Concerning current RHEL branches, they are too divergent to integrate into this scheme. Thus, commits are merged onto, and builds are done on the RHEL branches.
In this case, two pull requests will very likely be needed:

- one for the ``rhel<number>-branch``
- one for the ``master`` or ``<fedora number>-devel`` branch (if the change is not RHEL only)

Releases
---------

For specific Fedora version, the release process is as follows:

- ``<next Fedora number>-devel`` is merged onto ``<next Fedora number>-release``
- a release commit is made (which bumps version in spec file) & tagged

Concerning Fedora Rawhide, the release process is slightly different:

- a release commit is made (which bumps version in spec file) & tagged

Concerning the ``<next Fedora number>`` branches (which could also be called ``next stable release`` if we wanted to decouple our versioning from Fedora in the future):

- work which goes into the next Fedora goes to ``<next Fedora number>-devel``, which is periodically merged back to ``master``
- this way we can easily see what was developed in which Fedora timeframe and possibly due to given Fedora testing phase feedback (bugfixes, etc.)
- stuff we *don't* want to go to the next Fedora (too cutting edge, etc.) goes only to ``master`` branch
- commits specific to a given Fedora release (temporary fixes, etc.) go only to the ``<next Fedora number>-release`` branch
- the ``<next Fedora number>-release`` branch also contains release commits

Example for the F25 cycle
--------------------------

- master
- f25-devel
- f25-release

This would continue until F25 is released, after which we:

- drop the f25-devel branch
- keep f25-release as an inactive record of the f25 cycle
- branch f26-devel and f26-release from the master branch

This will result in the following branches for the F26 cycle:

- master
- f26-devel
- f26-release

Guidelines for Commits
-----------------------

Commit Messages
^^^^^^^^^^^^^^^^

The first line should be a succinct description of what the commit does, starting with capital and ending without a period ('.'). If your commit is fixing a bug in Red Hat's bugzilla instance, you should add `` (#123456)`` to the end of the first line of the commit message. The next line should be blank, followed (optionally) by a more in-depth description of your changes. Here's an example:

    Stop kickstart when space check fails

    Text mode kickstart behavior was inconsistent, it would allow an
    installation to continue even though the space check failed. Every other
    install method stops, letting the user add more space before continuing.

Commits for RHEL Branches
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are submitting a patch for any rhel-branch, the last line of your commit must identify the `JIRA issue <https://issues.redhat.com/projects/RHEL/issues/>`_ id it fixes, using the ``Resolves`` or ``Related`` keyword, e.g.:
``Resolves: jira#RHEL-11111``

or

``Related: jira#RHEL-12345``

Use ``Resolves`` if the patch fixes the core issue which caused the bug.
Use ``Related`` if the patch fixes an ancillary issue that is related to, but might not actually fix the bug.

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

Merging examples
----------------

Merging the Fedora ``devel`` branch back to the ``master`` branch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(Fedora 25 is used as an example, don't forget to use appropriate Fedora version.)

Checkout and pull the master branch:

``git checkout master``
``git pull``

Merge the Fedora devel branch to the master branch:

``git merge --no-ff f25-devel``

Push the merge to the remote:

``git push origin master``

Merging a GitHub pull request
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(Fedora 25 is used as an example, don't forget to use appropriate Fedora version.)

Press the green *Merge pull request* button on the pull request page.

If the pull request has been opened for:

- master
- f25-release
- rhel7-branch

Then you are done.

If the pull request has been opened for the ``f25-devel`` branch, then you also need to merge the ``f25-devel``
branch back to ``master`` once you merge your pull request (see "Merging the Fedora devel branch back to the master branch" above).

Merging a topic branch manually
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
(Fedora 25 is used as an example, don't forget to use appropriate Fedora version.)

Let's say that there is a topic branch called "fix_foo_with_bar" that should be merged to a given Anaconda non-topic branch.

Checkout the given target branch, pull it and merge your topic branch into it:

``git checkout <target branch>``
``git pull``
``git merge --no-ff fix_foo_with_bar``

Then push the merge to the remote:

``git push origin <target branch>``

If the <target branch> was one of:

- master
- f25-release
- rhel7-branch

Then you are done.

If the pull request has been opened for the ``f25-devel`` branch, then you also need to merge the ``f25-devel``
branch back to ``master`` once you merge your pull request (see "Merging the Fedora devel branch back to the master branch" above).

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
