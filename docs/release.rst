Rawhide release & package build
===============================

This guide describes how one create a new Anaconda release, from release commit to a new build in Koji.
While aimed primarily on core Anaconda developers and package maintainers doing official release and package build,
it could very well be useful for other use cases, such as for scratch builds or creation of custom Anaconda packages.
In that case just ignore all section that require you to be an Anaconda maintainer or developer. :)

0. prerequisites

- you need an up to date anaconda source code checkout
- you need to have commit access to the anaconda repository (so that you can push release commits)
- you need to have write access to the corresponding Fedora Zanata project so that you can push .pot file updates
- you need to have the ``rpmbuild`` and ``fedpkg`` tools installed
- you need to have the Fedora Kerberos based authentication setup
- you need to have committer access to the anaconda package on Fedora distgit


1. merge master to unstable

::

    git checkout master
    git pull
    git checkout unstable
    git pull
    git merge --no-ff master

2. do any changes that are needed to anaconda.spec.in

::

   vim anaconda.spec.in

3. do a release commit

::

    ./scripts/makebumpver -c --skip-zanata

4. check the commit and tag are correct

5. push the unstable branch to the remote

::

    git push unstable --tags

6. configure anaconda

::

    make clean
    ./autogen
    ./configure

# create tarball
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
    fedpkg switch-branch master
    git pull

10. switch to Fedora distgit folder and import the SRPM

::

    fedpkg import ~/rpmbuild/SRPMS/anaconda-<version>.src.rpm

11. this will stage a commit, check it's content and commit

 - the header should be: ``New version <version number>``
 - content of the commit message should be the same as the changelog in the spec for the given version

::

  git commit

12. push the update

::

    fedpkg push

13. start the build

::

    fedpkg build


Upcomming Fedora release & package build
========================================

Creating and anaconda release and build for an upcoming Fedora release is pretty similar to a Rawhide build
with a few key differences:

- the branches are named differently
- you need to create a Bodhi update so that the build actually reaches the stable package repository

So let's enumerate the steps that doe something differently in more detail (we use Fedora 26 in the CLI examples):

1. merge f<fedora version>-devel to f<fedora version>-release

::

    git checkout f26-devel
    git pull
    git checkout f26-release
    git pull
    git merge --no-ff master


5. push the f<fedora version>-release branch to the remote

::

    git push f26-release --tags


9. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the f<fedora version> branch & make sure it's up to date

::

    cd <some folder>
    fedpkg clone anaconda
    fedpkg switch-branch f26
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
