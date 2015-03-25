Anaconda Kickstart Documentation
================================

Anaconda uses `kickstart <https://github.com/rhinstaller/pykickstart>`_ to automate
installation and as a data store for the user interface. It also extends the kickstart
commands `documented here <https://fedoraproject.org/wiki/Anaconda/Kickstart>`_
by adding a new kickstart section named %anaconda where commands to control the behavior
of Anaconda will be defined.

.. contents:: %anaconda section commands


pwpolicy
========

pwpolicy <name> [--minlen=LENGTH] [--minquality=QUALITY] [--strict|notstrict] [--emptyok|notempty] [--changesok|nochanges]
    Set the policy to use for the named password entry.

    name
        Name of the password entry, currently supported values are: root, user and luks

    --minlen (**8**)
        Minimum password length. This is passed on to libpwquality.

    --minquality (**50**)
        Minimum libpwquality to consider good. When using --strict it will not allow
        passwords with a quality lower than this.

    --strict (**DEFAULT**)
        Strict password enforcement. Passwords not meeting the --minquality level will
        not be allowed.

    --notstrict
        Passwords not meeting the --minquality level will be allowed after Done is clicked
        twice.

    --emptyok (**DEFAULT**)
        Allow empty password.

    --notempty
        Don't allow an empty password

    --changesok
        Allow UI to be used to change the password/user when it has already been set in 
        the kickstart.

    --nochanges (**DEFAULT**)
        Do not allow UI to be used to change the password/user if it has been set in
        the kickstart.

The defaults for these are set in the /usr/share/anaconda/interactive-defaults.ks file
provided by Anaconda. If a product, such as Fedora Workstation, wishes to override them
then a product.img needs to be created with a new version of the file included.

When using a kickstart the defaults can be overridded by placing a %anaconda section into
the kickstart, like this::

    %anaconda
    pwpolicy root --minlen=10 --minquality=60 --strict --notempty --nochanges
    %end

.. note:: The commit message for pwpolicy included some incorrect examples.

