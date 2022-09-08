
.. include:: ../tests/README.rst

What to do if there are broken Rawhide dependencies
===================================================

As first step you have to find or create a fixed build of the package to get the RPM file.

Fix GitHub actions
------------------

The GitHub actions are using containers in most of the situation. So the fixup is simple here,
just modify the impacted `Dockerfile` and add a missing package there.

Note: Please use a comment FIXME / TODO with link to source of the issue and a message when we
should remove the hotfix RPM.

Fix Packit builds
-----------------

Edit the `.packit.yml` file and change the impacted part. If there is not already add an additional
repository to our public space.

::

    additional_repos:
      # This repository contains fixup of Rawhide broken environment.
      # Mainly useful when there is a package which is not yet in Rawhide but build is available.
      - "https://fedorapeople.org/groups/anaconda/repos/anaconda_fixup_repo/"


Next step is to upload the required packages to `fedorapeople.org`. Anyone who is part of the
`gitanaconda` group have access to that space.

Cleanup old repository.
::

    $ ssh <fedora_username>:fedorapeople.org
    $ cd /project/anaconda/repos/anaconda_fixup_repo/
    $ rm -rv *  # to remove the old directory structure
    

Create your repository locally and upload that.
::

    $ mkdir /tmp/anaconda-repo-fixup
    $ cd /tmp/anaconda-repo-fixup
    $ curl -OL <packages>
    $ createrepo .  # on older systems could be 'createrepo_c'
    $ scp -r * <fedora_username>:fedorapeople.org:/project/anaconda/repos/anaconda_fixup_repo

After the above is done, everything should be fixed and Packit should work again.

Fix ISO image refreshes for the WebUI tests
-------------------------------------------

In order to test the WebUI code we use the ISO images specified in `Cockpit's bots repository <https://github.com/cockpit-project/bots/tree/main/images>`_.

These ISO files are direct downloads from the official distribution server and their
`creation process is defined in bots repository <https://github.com/cockpit-project/bots/blob/main/images/scripts/fedora-rawhide-boot.bootstrap>`_.

The purpose of using these ISOs for the tests instead of downloading from the official server is to gate the image updates.

The default refresh period of the test images is one week, but they can also be `refreshed manually <https://github.com/cockpit-project/bots#refreshing-a-test-image>`_.

Image refreshes happen with `Pull Requests which update the current image SHA <https://github.com/cockpit-project/bots/pull/2981>`_.
The tests defined in `ui/webui/tests/` will run on the Pull request gating the `relevant to anaconda image refreshes <https://github.com/cockpit-project/bots/blob/main/lib/testmap.py>`_.

Image refreshes with successfull CI will be merged automagically from Cockpit team.

In the case an updated dependency makes the WebUI tests on the image refresh fail, the on-duty team
member is in charge of debugging the failure.

For this take the following steps:

    * Locally checkout the bots repository branch used in the failing refresh PR. The path to the local bots checkout should be the `ui/webui/bots`.
    * Create the test VM with the new image and debug by following the `WebUI test instructions <https://github.com/rhinstaller/anaconda/tree/master/ui/webui/test#readme>`_

When the reason for the breackage is identified there are two options to go forward:

    * If the failure comes from an intended change in behaviour adjust Anaconda or the tests
    * If the failure uncovers an actual regression, file bugs for the given Fedora components. If it does not look like the issue will be
      fixed quickly, work around in Anaconda or add a `naughty override file <https://github.com/cockpit-project/bots/tree/main/naughty/>`_, thus marking the expected failure pattern.

Fix a class of NPM errors that can break Web UI tests
-----------------------------------------------------

This issue manifests as failed build of Anaconda RPMs due to NPM errors, that prevents Web UI tests to be started at all. This differs
from an actual bug in NPM dependency specification or NPM package maintainers going all "it works on my machine" again in two key aspects:

    * the same NPM error suddenly breaks Web UI tests on *all* PRs
    * when Web UI tests are run locally outside of Cockpit CI the build succeeds and the test are started

What you are seeing is breakage in NPM caching the Cockpit CI is using to avoid issues with the massive NPM consumption of the infra.
The mechanism it usually works fine, but sometimes the cache update mechanism can get stuck, resulting in the cache going stale causing
this issue to manifest.

How to fix:

   * retry the test run on the PR - sometimes no all the builders are currently affected, retrying might run the test on different builder
   * report the issue to the Cockpit team - on #cockpit on Libera Chat IRC or as a new issue in https://github.com/cockpit-project/cockpit/issues

In the end, someone from the Cockpit team will tell the builders in the Cockpit infra to drop their cache, fixing the issue or the affected
builder possibly gets cleaned up by some automated mechanism over time.

Fix Web UI pixel tests
----------------------

So pixel tests fail on your PR - now what?

There are essentially two options:

    * the test uncovered a bug in your PR that needs to be fixed in the code
    * your PR changes the visual behavior of the Web UI in a valid manner and the pixel test needs to be fixed

We will cover the second option.

First make sure your PR is rebased on latest revision of the target branch. This is important as the issue you are seeing might have already been fixed by another PR that has since been merged.

If rebasing your PR did not fix the issue, and pixel tests still fail in CI on your PR, you will need to update one or more of the reference images.

::

    $ cd ui/webui
    $ make -f Makefile.am test/reference
    $ GITHUB_BASE=rhinstaller/anaconda ./test/common/pixel-tests pull

Next find the failing test in the PR CI test results and find the individual test that is failing. The results page shows an image comparison tool and in its header links to the new screenshot that no longer matches the expected picture:


::

    New <something>-fail-pixels.png on the left, reference on the right.

Download the screenshot into the `ui/webui/test/reference` folder and check it replaced an existing file - the new screenshot from the failed test will be named the same as one of the existing pictures that no longer match. For example:

::

    $ cd ui/webui/test/reference
    $ git diff --stat
    TestInstallationProgress-testBasic-installation-progress-step-fail-pixels.png | Bin 54445 -> 55628 bytes
    1 file changed, 0 insertions(+), 0 deletions(-)

If multiple pixel tests fail, this needs to be done once per each failing test.

Then from the `ui/webui` folder use a makefile target to update the reference image repo:

::

    $ cd ui/webui
    $ make update-reference-images
    test/common/pixel-tests push
    M	TestInstallationProgress-testBasic-installation-progress-step-fail-pixels.png
    Enumerating objects: 8, done.
    Counting objects: 100% (8/8), done.
    Delta compression using up to 12 threads
    Compressing objects: 100% (7/7), done.
    Writing objects: 100% (7/7), 164.70 KiB | 3.05 MiB/s, done.
    Total 7 (delta 0), reused 3 (delta 0), pack-reused 0
    To github.com:rhinstaller/pixel-test-reference
     * [new tag]         sha-bf9a391e45657f226a2a22b6cf377f499711444a -> sha-bf9a391e45657f226a2a22b6cf377f499711444a

This creates a new tag in the reference picture repository *and* also updates **and stages** the new reference repo submodule tag in the anaconda repo:

::

    $ git diff --cached
    diff --git a/ui/webui/test/reference b/ui/webui/test/reference
    index 54742ea13b..bf9a391e45 160000
    --- a/ui/webui/test/reference
    +++ b/ui/webui/test/reference
    @@ -1 +1 @@
    -Subproject commit 54742ea13bd271475a27769f8294ce16315e2e5e
    +Subproject commit bf9a391e45657f226a2a22b6cf377f499711444a

This makes sure the given Anaconda branch is pointing to the correct reference picture repo revision.

Now, to finally fix the failing pixel test, just make sure the submodule reference ends up as part of your PR - as a separate commit or possibly as part of a commit triggering the visual change. Once the PR is updated, the Cockpit CI should run again, including pixel test, which should now no longer fail due to an image miss-match.
