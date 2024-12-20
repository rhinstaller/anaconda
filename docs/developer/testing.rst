
.. include:: ../../tests/README.rst

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
