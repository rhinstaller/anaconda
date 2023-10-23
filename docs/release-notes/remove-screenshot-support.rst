:Type: GUI
:Summary: Remove screenshot support

:Description:
    It was previously possible to take a screenshot of the
    Anaconda GUI by pressing a global hotkey. This was
    never widely advertised & rather hard to use for anything
    useful, as it was also necessary to manually extract the
    resulting screenshots from the installation environment.

    Furthermore, with many installations happening in VMs,
    it is usually more convenient to take a screenshot using
    the VM software anyway.

    By dropping screenshot support, we can remove dependency
    on the ``keybinder3`` library as well as the necessary
    screenshot code in the GUI.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/5255
