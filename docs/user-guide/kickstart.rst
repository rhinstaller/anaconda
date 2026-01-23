Anaconda Kickstart Documentation
================================

:Authors:
    Brian C. Lane <bcl@redhat.com>

Anaconda uses `kickstart <https://github.com/pykickstart/pykickstart>`_ to parse and generate
kickstart files.

Automatically load the Kickstart file
-------------------------------------

If you need to load Kickstart file automatically you can store your Kickstart file as ``/ks.cfg``
into the storage device which is accessible during the boot process and is labeled as ``OEMDRV``.
Such a device is automatically discovered during boot and the Kickstart file will be used.

%anaconda
---------

The ``%anaconda`` kickstart section contains commands to control the behavior of Anaconda.

*Deprecated since Fedora 34.*

*Removed since Fedora 36.*

pwpolicy
--------

``program: pwpolicy <name> [--minlen=LENGTH] [--minquality=QUALITY] [--strict|notstrict] [--emptyok|notempty] [--changesok|nochanges]``
    Set the policy to use for the named password entry.

    ``name``
        Name of the password entry, currently supported values are: root, user and luks

    ``--minlen`` (6)
        Minimum password length. This is passed on to libpwquality.

    ``--minquality`` (1)
        Minimum libpwquality to consider good. When using ``--strict`` it will not allow
        passwords with a quality lower than this.

    ``--strict``
        Strict password enforcement. Passwords not meeting the ``--minquality`` level will
        not be allowed.

    ``--notstrict`` (**DEFAULT**)
        Passwords not meeting the ``--minquality`` level will be allowed after Done is clicked
        twice.

    ``--emptyok`` (**DEFAULT**)
        Allow empty password.

    ``--notempty``
        Don't allow an empty password

    ``--changesok``
        Allow UI to be used to change the password/user when it has already been set in
        the kickstart.

    ``--nochanges`` (DEFAULT)
        Do not allow UI to be used to change the password/user if it has been set in
        the kickstart.

The defaults for interactive installations are set in the ``/usr/share/anaconda/interactive-defaults.ks``
file provided by Anaconda. If a product, such as Fedora Workstation, wishes to override them
then a ``product.img`` needs to be created with a new version of the file included.

When using a kickstart the defaults can be overridded by placing an ``%anaconda`` section into
the kickstart, like this::

    %anaconda
    pwpolicy root --minlen=10 --minquality=60 --strict --notempty --nochanges
    %end

.. note:: The commit message for pwpolicy included some incorrect examples.

*Deprecated since Fedora 34.*

.. note:: You can use the configuration option ``password_policies``.

*Removed since Fedora 35.*


installclass
------------

``installclass --name=<name>``

    Require the specified install class to be used for the installation.
    Otherwise, the best available install class will be used.

    ``--name=``

        Name of the required install class.

*Removed since Fedora 30.*

.. note:: You can use the boot options ``inst.product`` and ``inst.variant``.
