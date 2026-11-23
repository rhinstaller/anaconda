:Type: Web UI
:Summary: Fedora installer media select the Web UI browser through packages

:Description:
    On Fedora installation media, the installed Web UI opener package now
    determines which browser opens the Anaconda web interface. The Fedora
    installer profiles no longer set the ``webui_web_engine`` option. If you
    build custom Fedora installation media, select the opener package for your
    preferred browser instead of setting that option in the profile.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/7428
