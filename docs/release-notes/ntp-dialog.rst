:Type: GUI
:Summary: Redesigned NTP server dialog (#1827683)

:Description:
    The NTP server dialog has been redesigned. The new look uses more traditional approach to
    management of lists (such as in `hexchat`).

    - The set of controls to add a new server is no longer present. Instead, a "blank" new server
      is added by clicking an "add" button. The details can be filled in by editing the server
      in the list, as was already possible.
    - The method to remove a server is now more intuitive. Users can simply click the "remove"
      button and the server is instantly removed from the list. Previously, users had to uncheck
      the "Use" checkbox for the server in the list and confirm the dialog.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/3538
    - https://bugzilla.redhat.com/show_bug.cgi?id=1827683
