Rawhide release & package build
===============================

This guide describes how one create a new Anaconda release, from release commit to a new build in Koji.
While aimed primarily on core Anaconda developers and package maintainers doing official release and package build,
it could very well be useful for other use cases, such as for scratch builds or creation of custom Anaconda packages.
In that case just ignore all section that require you to be an Anaconda maintainer or developer. :)

0. prerequisites

- you need an up to date anaconda source code checkout
- it is recommended to make the release on a fresh clone (prevents you from pushing local work into the upstream repository)
- you need to have commit access to the anaconda repository (so that you can push release commits)
- you need to have write access to the https://github.com/rhinstaller/anaconda-l10n localization repository
- you need to have the ``rpmbuild`` or ``mock`` and ``fedpkg`` tools installed
- you need to have the Fedora Kerberos based authentication setup
- you need to have committer access to the anaconda package on Fedora distgit

The (mostly) automated build path
---------------------------------
This is the default way of building the Anaconda package & should be used as long as the automation works.
If the automation is not working, fall back to the manual method until it has been fixed.

The overall workflow can be summarized to 3 steps:

- Anaconda release tarball build
- Packit PR in Fedora distgit
- start build in Fedora distgit

0. have an up to date Anaconda repo clone and ``main`` branch checked out

1. tag an Anaconda release:

::

    ./scripts/makebumpver -c

2. check the commit and tag are correct

3. push the main branch to the remote

::

      git push main --tags

4. this should trigger a GitHub workflow that will create a new Anaconda release + release tarball, taking ~10 minutes

5. visit https://github.com/rhinstaller/anaconda/releases and check the new draft release look correct

6. if the release looks fine, click the edit icon and release the draft as a regular non-draft release

7. this will trigger Packit to open a PR in Fedora distgit https://src.fedoraproject.org/rpms/anaconda/pull-requests in the next ~10 minutes

8. check the PR looks correct and ideally wait for all the CI jobs started on the PR to run to the end & investigate any failures

9. if all is good enough, merge the PR

10. use fedpkg to trigger the build (no, there is no button for this just yet...)

::

      fedpkg clone anaconda
      cd anaconda
      fedpkg switch-branch rawhide
      fedpkg build

if you already have a distgit checkout, you can do just:

::

      fedpkg switch-branch rawhide
      git pull
      fedpkg build

If this update contains non backwards compatible changes that might break another package, ex
`anaconda-webui` you need to follow the procedure below

::

      fedpkg switch-branch rawhide
      git pull
      fedpkg request-side-tag
      fedpkg build --target=${SIDE_TAG}

This process is documented in more detail in the
[Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/package-maintainers/Package_Update_Guide/#multiple_packages)

11. this should start the package build in koji - wait for it to succeed or debug any failures

Using the manual ``rpmbuild`` path
----------------------------------
This is more standard and stable way to make Anaconda release. The drawback of this method is you need to have
everything installed locally so you are required to install a lot of dependencies to your system. For the mock
environment way see mock path below. It is also fully manual.


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
    ./autogen.sh
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

9. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the rawhide branch & make sure it's up to date

::

    cd <some folder>
    fedpkg clone anaconda
    cd anaconda
    fedpkg switch-branch rawhide
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

14. check repository on path returned by the above command and push if it's correct


Upcoming Fedora release & package build
========================================

Creating an anaconda release and build for an upcoming Fedora release is pretty similar to a Rawhide build
with a few key differences:

- the upstream project branch is named fedora-<version>
- the distgit branch is named f<version>
- you need to create a Bodhi update so that the build actually reaches the stable package repository

So let's enumerate the steps that do something differently in more detail (we use Fedora 28 in the CLI examples):

9. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the f<version> branch & make sure it's up to date

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

    fedpkg update

Next an update template should open in your editor of choice - fill it out, save it & quite the editor.
A link to the update should be returned and you should also start getting regular spam from Bodhi when
anything remotely interesting happens with the update. :)

Releasing during a Fedora code freeze
=====================================

There are two generally multi-week phases during which the upcoming Fedora release development a temporary code freeze:

- the Beta freeze
- the Final freeze

During these periods of time only accepted freeze exceptions and blocker fixes are allowed to reach the stable repository.

So don't merge any PRs to the fedora-<version> upstream branch during a Fedora freeze that don't fix a freeze exception or a release blocker.

If there is a merged PR that has not been approved for a FE or release blocker, it should be reverted before the next Anaconda build
targeting the frozen Fedora.

Branching for the next Fedora release
=====================================

Anaconda uses separate branch for each Fedora release to make parallel Anaconda development for Rawhide and next Fedora release possible.
The branch is named fedora-<version>.

The branch contains release commits and any changes suitable for the given branched Fedora version.

This might be both "regular" changes merged and released outside of a freeze period as well as approved Fedora freeze-exceptions
and release blocker fixes.


Create new localization directory for Anaconda
----------------------------------------------

First thing which needs to be done before branching in Anaconda is to create a new localization directory which will be used by the new Anaconda branch.

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


Adjust localization update automation
-------------------------------------

In the ``anaconda-l10n`` repository, the update automation needs to work on the new directory.

Edit the file ``.github/workflows/pot-file-update.yaml``:

::

   vim .github/workflows/pot-file-update.yaml

Update the matrix. For example, for f39 we had:

::

      matrix:
        branch: [ main, f39, rhel-9 ]
        include:
          (...)
          - branch: f39
            anaconda-branch: fedora-39
            container-tag: fedora-39

Commit these changes:

::

   git commit -m "infra: Adjust pot updates for Fedora <version>"

Push the changes:

::

   git push origin


Enable Cockpit CI for the new branch
-------------------------------------------

Anaconda is using the Cockpit CI infrastructure to run Web UI test. Cockpit CI tests are triggered
automatically for all `listed <https://github.com/cockpit-project/bots/blob/main/lib/testmap.py>`_ projects and per-project branches. To enable Cockpit CI in automatic mode for the new Fedora branch, our new fedora-<version> upstream branch needs to be added under the 'rhinstaller/anaconda' key in the file. See the previous PR (for F39) to see how this is to be done:

https://github.com/cockpit-project/bots/pull/5176

How to branch Anaconda
----------------------

First make sure that localization branch for the next Fedora is already created.

Create the fedora-<version> upstream branch:

::

    git checkout main
    git pull
    git checkout -b fedora-<version>

Edit branch specific settings:

::

   vim .branch-variables.yml

And change content according to comments in the file.

Then rebuild everything that is templatized:

::

    make -f Makefile.am reload-infra

This should set up infrastructure and some other parts like makefile variables and pykickstart version used.

Lastly it is necessary to set up updated l10n commit hash - check the commit hash of the ``anaconda-l10n`` repo,
the one where the new f<version> folder has been added and put the hash to the ``GIT_L10N_SHA`` variable in the
``po/l10n-config.mk`` file.

This is necessary for the Web UI related translation pinning to work & l10n branching checks to pass.

Verify the changes and commit:

::

    git commit -a -m "Set up the fedora-NN branch"

After doing this, please verify that Pykickstart supports Fedora <version> and <version + 1>
if not, please file an `issue <https://github.com/pykickstart/pykickstart/issues>`_ on the
Pykickstart project. The Pykickstart support for future release of Fedora will prevent
issues during the next branching.

Check if everything is correctly set:

::

   make check-branching

If everything works correctly you can push the branch to the origin (``-u`` makes sure to setup tracking) :

::

    git checkout fedora-<version>
    git push -u origin fedora-<version>

After the branching is done, you also need to update infrastructure on the ``main`` branch. Switch to that branch:

::

    git switch main

Edit branch specific settings:

::

   vim .branch-variables.yml

In the file, set the correct branched Fedora version, then rebuild the files, check and commit.
Expect changes only in Github workflows that generate containers etc. for multiple branches.

::

    make -f Makefile.am reload-infra
    git commit -a -m "infra: Configure for the new fedora-NN branch"

Then, finally, push the updated main branch:

::

    git push origin main

Container rebuilds after branching
----------------------------------

Container rebuilds currently do not happen automatically after branching. So do not forget to rebuild
all relevant containers after Fedora branching.


How to add release version for next Fedora
------------------------------------------

The current practise is to keep the Rawhide major & minor version from which the
given Anaconda was branched as-is and add a third version number (the release number
in the NVR nomenclature) and bump that when releasing a new Anaconda for the
upcoming Fedora release.

For example, for the F27 branching:

- the last Rawhide Anaconda release was 27.20
- so the first F27 Anaconda release will be 27.20.1, the next 27.20.2 and so on

First checkout the ``fedora-<version>`` upstream branch:

::

    git checkout fedora-<version>

Next add the third (release) version number:

::

    ./scripts/makebumpver -c --add-version-number

If everything looks fine (changelog, the version number & tag) push the changes to the origin:

::

    git push origin fedora-<version> --tags

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


How to use a new Python version
-------------------------------

Fedora changes Python version from time to time.

The only place where Python is explicitly listed in Anaconda code base and needs changing is in
``scripts/makeupdates``::

    # The Python site-packages path for pyanaconda.
    SITE_PACKAGES_PATH = "./usr/lib64/python3.12/site-packages/"

If this path is not correct, updates images "mysteriously stop working".

Unfortunately, Python release timing is not well aligned with Fedora, so Rawhide mostly gets
a Python release candidate (rc). This affects two things:

- Usually, the stability of the interpreter is good, but there are deprecations and removals in the
  standard library.

- Pylint often does not handle unreleased Python, because it touches private interpreter
  and library internals. The only recourse is often to disable it and wait for the official Python
  release. Fortunately, ruff handles linting too.


How to collect release notes after branched GA release
------------------------------------------------------

Release notes are collected in ``docs/release-notes/*.rst``. When a major Fedora version goes GA,
these should be collected into the file ``docs/release-notes.rst``. To do so:

0. Work on the main branch. Edit the file. New content is added on top.
1. Create a heading for new Fedora version and subheadings for the broader areas. The previous
   entry can provide some guidance.
2. Copy the individual release notes contents into the document according to the headings, and edit
   the contents to use the same form as in the document. Don't spend too much time on formatting,
   just make sure it renders correctly.
3. Delete the individual release note files.
4. If you know there are some other major features missing, add them to the document too.
5. Commit and make a PR.

The branch used for the release is not touched. This might be surprising, but docs are always used
from the ``main`` branch.
