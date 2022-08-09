:Type: GUI
:Summary: Do not include swap in space estimate if swap is disabled (#2068290)

:Description:
   During automatic partitioning the disk spoke estimates the space required for the installation
   and if there isn't enough free space it display a warning dialog suggesting more space should
   be reclaimed.

   This estimate included the recommended swap size even when swap wasn't configured to be created.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2068290
    - https://github.com/rhinstaller/anaconda/pull/4238
