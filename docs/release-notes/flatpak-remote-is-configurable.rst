:Type: Flatpak
:Summary: Remote repository for Flatpaks after deployment are now configurable

:Description:
    Currently when OSTree installation detects Flatpak repository in the installation media
    these Flatpaks are deployed and the remote was hardcoded to remote Fedora. This remote
    is then used for updating the Flatpaks after installation.

    After this change Flatpak remote can be set by ``flatpak_remote`` key in the configuration
    file.
