Rawhide release & package build
===============================

This guide describes how one create a new Anaconda release, from release commit to a new build in Koji.
While aimed primarily on core Anaconda developers and package maintainers doing official release and package build,
it could very well be useful for other use cases, such as for scratch builds or creation of custom Anaconda packages.
In that case just ignore all section that require you to be an Anaconda maintainer or developer. :)

0. prerequisites

- you need an up to date anaconda source code checkout
- it is recommended to make the release on a fresh clone (prevent you from pushing local work into the upstream repository)
- you need to have commit access to the anaconda repository (so that you can push release commits)
- you need to have write access to the https://github.com/rhinstaller/anaconda-l10n localization repository
- you need to have the ``rpmbuild`` or ``mock`` and ``fedpkg`` tools installed
- you need to have the Fedora Kerberos based authentication setup
- you need to have committer access to the anaconda package on Fedora distgit

Using ``rpmbuild`` path
-----------------------
This is more standard and stable way to make Anaconda release. The drawback of this method is you need to have
everything installed locally so you are required to install a lot of dependencies to your system. For the mock
environment way see mock path below.


1. do any changes that are needed to anaconda.spec.in

::

   vim anaconda.spec.in

2. do a release commit

::

    ./scripts/makebumpver -c

3. check the commit and tag are correct

4. push the main branch to the remote

::

    git push main --tags

5. configure anaconda

::

    make clean
    ./autogen
    ./configure

6. create tarball

::

   make release

7. copy tarball to SOURCES

::

    cp anaconda-*.tar.bz2 ~/rpmbuild/SOURCES/

8. create SRPM

::

    rpmbuild -bs --nodeps anaconda.spec

9. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the master branch & make sure it's up to date

::

    cd <some folder>
    fedpkg clone anaconda
    cd anaconda
    fedpkg switch-branch master
    git pull

10. switch to Fedora distgit folder and import the SRPM

::

    fedpkg import ~/rpmbuild/SRPMS/anaconda-<version>.src.rpm

11. this will stage a commit, check it's content and commit

 - Do not forget to replace the ``<new-version>`` with correct version!!

::

  fedpkg commit --with-changelog --message "New version <new-version>"

12. push the update

::

    fedpkg push

13. start the build

::

    fedpkg build

14. push new translations

::

    make po-push

15. check repository on path returned by the above command and push if it's correct


Upcoming Fedora release & package build
========================================

Creating and anaconda release and build for an upcoming Fedora release is pretty similar to a Rawhide build
with a few key differences:

- the branches are named differently
- you need to create a Bodhi update so that the build actually reaches the stable package repository

So let's enumerate the steps that doe something differently in more detail (we use Fedora 28 in the CLI examples):

1. merge f<fedora version>-devel to f<fedora version>-release

::

    git checkout f28-devel
    git pull
    git checkout f28-release
    git pull
    git merge --no-ff f28-devel


5. push the f<fedora version>-release branch to the remote

::

    git push f28-release --tags


9. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the f<fedora version> branch & make sure it's up to date

::

    cd <some folder>
    fedpkg clone anaconda
    fedpkg switch-branch f28
    git pull


As this is a build for a upcoming Fedora release we need to also submit a Bodhi update:

14. create a Bodhi update from the command line (from the distgit folder)

- you can only do this once the Koji build finishes successfully
- it's also possible to create the update from the Bodhi web UI

::

    fedpkg --update

Next an update template should open in your editor of choice - fill it out, save it & quite the editor.
A link to the update should be returned and you should also start getting regular spam from Bodhi when
anything remotely interesting happens with the update. :)



Releasing during a Fedora code freeze
=====================================

There are two generally multi-week phases during which the upcoming Fedora release development a temporary code freeze:

- the Beta freeze
- the Final freeze

During these periods of time only accepted freeze exceptions and blocker fixes are allowed to reach the stable repository.

To reconcile the freeze concept with the idea that the -devel branch should should be always open for development and that
it should be always possible to merge the -devel branch to the -release branch (even just for CI requirements) we have
decided temporarily use downstream patches for package builds during the freeze.

That way we avoid freeze induced cherry picks that might break merges in the future and can easily drop the patches once
the freeze is over and resume the normal merge-devel-to-release workflow.

How it should work
------------------

Once Fedora enters a freeze:

- all freeze exceptions and blocker fixes are cherry picked into patch files
- patch files are added to distgit only as downstream patches

Once Fedora exits the freeze:

- drop the downstream patches and do merge based releases as before


Branching for the next Fedora release
=====================================

Anaconda uses separate branches for each Fedora release to make parallel Anaconda development for Rawhide and next Fedora possible.
The branches are named like this:

- f<number>-devel
- f<number>-release

The ``-devel`` branch is where code changes go and it is periodically merged to the master branch.
The ``-release`` branch contains release commits and any Fedora version specific hotfixes.

Create new localization branch for Anaconda
-------------------------------------------

First thing which needs to be done before branching in Anaconda is to create a new localization branch which will be used by the new Anaconda branch.

Start by cloning translation repository (ideally outside of Anaconda git) and enter this repository:

::

   git clone git@github.com:rhinstaller/anaconda-l10n.git
   cd anaconda-l10n

Create a new localization directory from ``main`` directory:

::

   cp -r main f<version>

Add the new folder to git:

::

   git add f<version>

Commit these changes:

::

   git commit -m "Branch new Fedora <version> from main"

Push new localization directory. This will be automatically discovered and added by
`Weblate <https://translate.fedoraproject.org/projects/anaconda/>`_ service:

::

   git push origin

How to branch Anaconda
----------------------

FIXME: This does not reflect latest changes required by containers for CI and tests.

First make sure that localization branch for the next Fedora is already created.

Create the ``-devel`` branch:

::

    git checkout main
    git pull
    git checkout -b f<version>-devel

Create the ``-release`` branch:

::

    git checkout master
    git pull
    git checkout -b f<version>-release

Switch to f<version>-release branch for Fedora specific settings:

::

   git checkout f<version>-release

Edit branch specific settings. This have to be done on f<version>-release branch only:

::

   vim ./branch-config.mk

And change content according to comments in the file.


Then correct pykickstart version for the new Fedora release by changing all occurrences of
the DEVEL constant imported from pykickstart for the F<version> constant, for example:

::

    from pykickstart.version import DEVEL as VERSION

to

::

    from pykickstart.version import F29 as VERSION


Pykickstart generally does not do per Fedora version branches, so this needs to be done
in the Fedora version specific branch on Anaconda side.

Commit the result. The commit will become one of the few exclusive release branch commits,
as we can't let it be merged back to master via the devel branch for obvious reasons.


Check if everything is correctly set:

::

   make check-branching


If everything works correctly you can push the branches to the origin (``-u`` makes sure to setup tracking) :

::

    git checkout f<version>-devel
    git push -u origin f<version>-devel

::

    git checkout f<version>-release
    git push -u origin f<version>-release


How to add release version for next Fedora
------------------------------------------

The current practise is to keep the Rawhide major & minor version from which the
given Anaconda was branched as-is and add a third version number (the release number
in the NVR nomenclature) and bump that when releasing a new Anaconda for the
upcoming Fedora release.

For example, for the F27 branching:

- the last Rawhide Anaconda release was 27.20
- so the first F27 Anaconda release will be 27.20.1, the next 27.20.2 and so on

First checkout the ``f<version>-release`` branch and merge ``f<version>-devel`` into it:

::

    git checkout f<version>-release
    git merge --no-ff f<version>-devel


Next add the third (release) version number:

::

    ./scripts/makebumpver -c --add-version-number

If everything looks fine (changelog, the version number & tag) push the changes to the origin:

::

    git push origin f<version>-release --tags

Then continue with the normal Upcoming Fedora Anaconda build process.

How to bump Rawhide Anaconda version
------------------------------------

- major version becomes major version ``+1``
- minor version is set to 1

For example, for the F27 branching:

- at the time of branching the Rawhide version was ``27.20``
- after the bump the version is ``28.1``

Make sure you are in the Rawhide branch:

::

    git checkout main

Do the major version bump and verify that the output looks correct:

::

    ./scripts/makebumpver -c --bump-major-version

If everything looks fine (changelog, new major version & the tag) push the changes to the origin:

::

    git push origin main --tags

Then continue with the normal Rawhide Anaconda build process.
