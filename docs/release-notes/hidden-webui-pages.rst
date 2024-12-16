:Type: Configuration
:Summary: Support for Hiding Specific Pages in the Web UI

    :Description:
    The Web UI now supports hiding specific pages by adding their page IDs to the
    hidden-webui-pages option in the anaconda.conf file.

    For example, in the Workstation ISO, the 'Account Creation' page shoult not be displayed,
    as this step is handled by GNOME Initial Setup during first boot. To hide this page,
    the following configuration is be added:

    hidden-webui-pages = anaconda-screen-accounts

    This feature allows tailoring the Web UI experience to meet the specific needs of
    different ISOs or spins.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/6047
