:Type: UI
:Summary: Unify the help support

:Description:
    Unify the help support on RHEL and Fedora using new mapping files.
    The mappings files are located in the root of the help directory.
    For example for RHEL, they are expected to be at::

        /usr/share/anaconda/help/rhel/anaconda-gui.json
        /usr/share/anaconda/help/rhel/anaconda-tui.json

    The mapping files contain data about the available help content.
    The UI screens are identified by a unique screen id returned by
    the ``get_screen_id`` method, for example ``installation-summary``.
    The help content is defined by a relative path to a help file and
    (optionally) a name of an anchor in the help file.

    For example::

        {
          "_comment_": [
            "This is a comment",
            "with multiple lines."
          ],
          "_default_": {
            "file": "default-help.xml",
            "anchor": "",
          },
          "installation-summary": {
            "file": "anaconda-help.xml",
            "anchor": "",
          },
          "user-configuration": {
            "file": "anaconda-help.xml",
            "anchor": "creating-a-user-account"
          }
        }

    If the mapping file doesn't provide the requested help content,
    we will use the default one if specified. Comments are ignored.

    The ``helpFile`` attribute is removed from the UI class. Specify
    a screen id or redefine the help handler to provide the built-in help.

    The ``default_help_pages`` configuration option is removed. Use
    the ``_default_`` help id in the help mapping file to define default
    help content.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/3575
