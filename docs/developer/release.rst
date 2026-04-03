Rawhide release & package build
===============================

This guide describes how one create a new Anaconda release, from release commit to a new build in Koji.
While aimed primarily on core Anaconda developers and package maintainers doing official release and package build,
it could very well be useful for other use cases, such as for scratch builds or creation of custom Anaconda packages.
In that case just ignore all section that require you to be an Anaconda maintainer or developer. :)

Prerequisites
-------------

For the automation path (preferred):

- you need to have committer access to the anaconda package on Fedora distgit

For the manual path:

- you need an up to date anaconda source code checkout
- it is recommended to make the release on a fresh clone (prevents you from pushing local work into the upstream repository)
- you need to have commit access to the anaconda repository (so that you can push release commits)
- you need to have write access to the https://github.com/rhinstaller/anaconda-l10n localization repository
- you need to have the ``rpmbuild`` or ``mock`` and ``fedpkg`` tools installed
- you need to have the Fedora Kerberos based authentication setup
- you need to have committer access to the anaconda package on Fedora distgit

Automation Path (Preferred)
---------------------------
This is the default way of building the Anaconda package & should be used as long as the automation works.
If the automation is not working, fall back to the manual method until it has been fixed.

The default release workflow is now automated through GitHub and Packit:

- GitHub workflow generates the release & tarball
- Packit creates PRs in Fedora distgit and handles Koji + Bodhi automatically

Step 1. Trigger the GitHub release workflow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Trigger the `release workflow <https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml>`_ in GitHub Actions:

- Click “Run workflow" and select the desired branch

The workflow will:

- Create the release commit and tag
- Build the release tarball
- Create a GitHub release

➡️  If this fails, continue with `Manual Step 1 <#manual-path-step-1-tag-and-push-release>`_.

✅ Otherwise, continue with `Step 2 <#step-2-verify-the-github-release>`_

Step 2: Verify the GitHub Release
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each time a tag is pushed, the `release-from-tag GitHub workflow <https://github.com/rhinstaller/anaconda/actions/workflows/release-from-tag.yml>`_
is triggered. This workflow generates a new release and builds the corresponding tarball.

Visit https://github.com/rhinstaller/anaconda/releases and verify the new release.

✅ Continue with `Step 3 <#step-3-review-and-merge-the-fedora-distgit-pr>`_


Step 3: Review and Merge the Fedora Distgit PR
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After a GitHub release is published, Packit will automatically open a pull request in `Fedora distgit
<https://src.fedoraproject.org/rpms/anaconda/pull-requests>`_.

If all is good enough, merge the PR.

➡️  If this fails try to find the handled release in the `Packit dashboard <https://dashboard.packit.dev/projects/github.com/rhinstaller/anaconda>`_
and then contact the Packit team for help.

✅ Otherwise, continue with `Step 4 <#step-4-koji-build-and-bodhi-update-handled-by-packit>`_

Step 4: Koji Build and Bodhi Update (Handled by Packit)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After merging the dist-git PR, **Packit will take over** and:

- Trigger a **Koji build** for the package(s).
- **Create a Bodhi update** once the build succeeds.

➡️  If this fails, continue with `Manual Step 4 <#manual-path-step-4-manual-koji-build>`_.

Skipping a release of one of the packages 
"""""""""""""""""""""""""""""""""""""""""

Triggering the `release workflow <https://github.com/rhinstaller/anaconda/actions/workflows/release-automatically.yml>`_
in the anaconda repository only affects the anaconda package. It does not release anaconda-webui. To
release anaconda-webui, you must follow its dedicated `release procedure
<https://github.com/rhinstaller/anaconda-webui/blob/main/docs/release.rst>`_.

If you are releasing both packages, Packit will automatically handle a combined Koji side tag build
and Bodhi update.

However, if you are releasing only one of the two packages, you need to make sure that Koji has a
tag for the latest released version of the other package — so that a coordinated side tag
build can proceed.

To do this:

In the last merged dist-git pull request of the package you are not releasing, add the following
comment::

    /packit koji-tag

📝 Note: This comment can be added before or after merging the PR — the timing doesn’t matter.

This tells Packit to tag the most recent build of that package with the side tag used for the
release of the other one.

This process applies in both directions:

* Releasing anaconda, but not anaconda-webui → tag the latest anaconda-webui PR.

* Releasing anaconda-webui, but not anaconda → tag the latest anaconda PR.


For more information, see the official `Packit multiple package release guide
<https://packit.dev/docs/fedora-releases-guide/releasing-multiple-packages#skipping-release-of-some-packages>`_.


Manual Path - Fallback
----------------------

Manual Path – Step 1: Tag and Push Release
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

0. Have an up to date Anaconda repo clone and ``main`` branch checked out

1. Tag an Anaconda release:

::

    ./scripts/makebumpver -c

2. Check the commit and tag are correct

3. Push the main branch to the remote

::

      git push main --tags

✅ Continue with `Step 2 <#step-2-verify-the-github-release>`_

Manual Path - Step 4: Manual Koji Build
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the manual way of building the Anaconda package. It is not recommended to use this method unless the automation is broken.

Use fedpkg to trigger the build (no, there is no button for this just yet...)

::

      fedpkg clone anaconda
      cd anaconda
      fedpkg switch-branch rawhide
      fedpkg build

If you already have a distgit checkout, you can do just:

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
`Fedora Packaging Guidelines <https://docs.fedoraproject.org/en-US/package-maintainers/Package_Update_Guide/#multiple_packages>`_.

This should start the package build in koji - wait for it to succeed or debug any failures.

Using the manual ``rpmbuild`` path
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
----------------------------------------

Creating an anaconda release and build for an upcoming Fedora release is pretty similar to a Rawhide build
with a few key differences:

- the upstream project branch is named fedora-<version>
- the distgit branch is named f<version>

Bodhi updates are handled by packit, so you don't need to do this manually. In case you need to do this manually,
you can use the following steps:

1. if you don't have it yet checkout Anaconda from Fedora distgit, switch to the f<version> branch & make sure it's up to date

::

    cd <some folder>
    fedpkg clone anaconda
    fedpkg switch-branch f28
    git pull


2. create a Bodhi update from the command line (from the distgit folder)

- you can only do this once the Koji build finishes successfully
- it's also possible to create the update from the Bodhi web UI

::

    fedpkg update

Next an update template should open in your editor of choice - fill it out, save it & quite the editor.
A link to the update should be returned and you should also start getting regular spam from Bodhi when
anything remotely interesting happens with the update. :)

Releasing during a Fedora code freeze
-------------------------------------

There are two generally multi-week phases during which the upcoming Fedora release development a temporary code freeze:

- the Beta freeze
- the Final freeze

During these freeze periods only accepted freeze exceptions and blocker fixes are allowed to reach the Fedora package repository.

We can’t realistically also enforce this policy on the ``main`` branch, as that would effectively freeze it too. Instead,
we handle the Fedora under development during the freeze period through a patch build.

Unlike a regular build, where each Anaconda package release generates a new tarball, a patch build applies one or more patches
on top of the existing tarball at build time. These patches include the approved blocker fixes and freeze exceptions.

A patch build by example in a few easy steps:

1. identify which PRs fall under the approved blocker bug or freeze exception & make sure each commit has

::

    Resolves: rhbz#<bug_id> (in this example we will use 1234)

2. cherry pick the commit using the ``git format-patch command``, resulting in one patch file per commit in the PR

Alternatively you can also fetch patches directly from the Anaconda GitHub repo using the URL patch generation feature:

For example this fetches a patch for all commits in PR number 6597:

::

    wget https://github.com/rhinstaller/anaconda/pull/6597.patch

It is also possible to fetch individual commits by their SHA hash:

::
    wget https://github.com/rhinstaller/anaconda/commit/$SHA.patch

This is the simplest way of getting suitable patch files, provided no changes are needed for them to
apply cleanly to the Anaconda version that is stored in the dist git tarball.

If these patches generated by GitHub are sufficient, you can go to step 5 next.

3. note that you should first checkout the tag corresponding to the release tarball (lets say the Anaconda version version in the tarball is 50.2 - checkout the ``anaconda-50.2`` tag)

4. then use ``git format-patch`` to create the patch files - this way the patches should apply cleanly on top of the Anaconda version that is in the tarball

5. clone the ``anaconda`` repo from Fedora distgit (``fedpkg clone anaconda``) with fedpkg or use an existing up to date checkout

6. switch to corresponding Fedora distgit branch (for Fedora 43 this would be ``fedpkg switch-branch f43``)

7. copy over the patch files you have created and add them to git (``git add 0001-foo.patch``, etc.)

8. add ``Patch<number>: patch_file_name`` lines under the ``Source0:`` line, like this (also include a comment describing why the patch is there):

::

    # Workaround for https://bugzilla.redhat.com/show_bug.cgi?id=<1234>
    Patch0: 0001-foo.patch

9. then bump the ``Release:`` number - say the main version was 50.2 and release was 1 - bump it to 2, resulting in version 50.2-2.

::

    Release: 1%{?dist}

becomes

::

    Release: 2%{?dist}

Bump ``Release:`` like this by one for any followup patch build.

10. add changelog entry

::

    * Thu Oct 24 2024 Some Person <sperson@redhat.com> - 50.2-2
    - Add patch with fix for foo (#1234) (sperson)

11. ``git add`` the changed spec file and commit with a suitable commit message, for example like this:

::

    Add patch that fixes foo

    Resolves: rhbz#1234

12. push the commit to a topic branch and open a distgit PR from it, which has the benefit of doing a scratch and running the same distgit CI as for a regular build

13. wait for the distgit PR CI to pass (or fixup and issues until unit it passes) and merge the PR - package build as well as Bodhi update creation should be triggered automatically

14. notify Fedora QA so that they are aware that an Anaconda build fix blocker fix/freeze exception/both is available

You can continue doing this workflow, adding more patches for as long as necessary, but the expectation is that eventually the freeze period will end
& the next regular rebase build will contain all the patches in its tarball. The next regular (e.g. rebase with a new tarball) release will drop
the patches and set ``Release:`` back to 1.

If the patch build is done during the final freeze, it might remain in place after Fedora GA on the given Fedora distgit branch (e.g. ``f43``).


Branching for the next Fedora release
-------------------------------------

Anaconda uses separate branch for each Fedora release to make parallel Anaconda development for Rawhide and next Fedora release possible.
The branch is named fedora-<version>.

The branch contains release commits and any changes suitable for the given branched Fedora version.

This might be both "regular" changes merged and released outside of a freeze period as well as approved Fedora freeze-exceptions
and release blocker fixes.


Create new localization directory for Anaconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anaconda is using the Cockpit CI infrastructure to run Web UI test. Cockpit CI tests are triggered
automatically for all `listed <https://github.com/cockpit-project/bots/blob/main/lib/testmap.py>`_ projects and per-project branches. To enable Cockpit CI in automatic mode for the new Fedora branch, our new fedora-<version> upstream branch needs to be added under the 'rhinstaller/anaconda' key in the file. See the previous PR (for F39) to see how this is to be done:

https://github.com/cockpit-project/bots/pull/5176

Enabling CI and other infra for branched Fedora
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To enable testing and releases for the branched Fedora from main:

1. **Build containers:** Containers are not built automatically for the branched Fedora. Run the `Rebuild container images
   <https://github.com/rhinstaller/anaconda/actions/workflows/container-rebuild-action.yml>`_
   workflow with **branch** ``main`` and **container-tag** ``fedora-N``.
   Wait for success so images are on quay.io.

2. **Edit** ``.branch-variables.yml``: set **rawhide_fedora_version** and add the new fedora release
   to **supported_releases**.

3. **Regenerate infra:** ``make -f Makefile.am reload-infra``, then commit and push to ``main``.

How to branch Anaconda
^^^^^^^^^^^^^^^^^^^^^^

This is required for RHEL branches. For Fedora, it is also needed when rawhide development
must diverge from the branched Fedora (e.g. a dedicated ``fedora-<version>`` branch).

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

How to add release version for next Fedora
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
