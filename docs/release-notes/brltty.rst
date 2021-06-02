:Type: Accessibility
:Summary: Server images offer limited support for braille devices

:Description:
    The Server image (boot.iso) now contains the `brltty` accessibility software.
    This means that some braille output devices can be automatically detected and used.

    This feature works only in text mode, started with the `inst.text` boot option.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=1584679
    - https://github.com/rhinstaller/anaconda/pull/3434
