:Type: GUI
:Summary: Dir and image installations run only in the non-interactive text mode now

:Description:
    Anaconda now requires a fully defined kickstart file for installations into a local image
    (via the ``--image`` cmdline option) or a local directory (via the ``--dirinstall`` cmdline
    option) and these installations can run only in a non-interactive text-based user interface.
    The ``anaconda`` and ``livemedia-creator`` tools can be used for these types of installations
    with the following changes:

    * If a user requests a dir or image installation, Anaconda runs in the text mode.
    * If the user doesn't specify a kickstart file, Anaconda reports an error and aborts.
    * If the specified kickstart file is incomplete, Anaconda reports an error and aborts.
    * All options for specifying the user interface are ignored.

:Links:
    - https://fedoraproject.org/wiki/Changes/Anaconda_dir_and_image_installations_in_automated_text_mode
    - https://github.com/rhinstaller/anaconda/pull/5447
