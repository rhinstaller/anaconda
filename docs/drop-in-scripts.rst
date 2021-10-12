Drop-in ``%post`` scripts
=========================

:Authors:
    Vladimir Slavik <vslavik@redhat.com>

Anaconda automatically loads custom ``%post`` kickstart scripts from the drop directory
``/usr/share/anaconda/post-scripts``. File names of these scripts must end with "ks", eg.
``do-something.ks```. If the user does not provide any kickstart to the
installer, the scripts from this directory are still loaded and run.

These drop-in scripts are executed at the end of installation, after any ``%post`` scripts loaded
from the kickstart file supplied for the installation. They are also handled differently than
scripts from kickstart supplied by user: Logging of the drop-in scripts is different, and they are
not saved to the "output" kickstart file ``anaconda-ks.cfg``.

Files with these scripts should contain only comments and the ``%post`` script section(s), such as:

::

    # Register foo with bar for baz
    # John Doe, 2048 AD

    %post
    bar --register foo
    %end

    %post --interpreter=/usr/bin/python
    import baz
    baz.update_from_bar("foo")
    baz.rewrite_config()
    %end

All standard features of the ``%post`` script sections apply.

**WARNING:**

* This functionality is NOT guaranteed to be a stable API.
* Behavior for kickstart contents other than post scripts in these files is undefined.
