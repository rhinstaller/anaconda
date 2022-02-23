
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
