:Type: GUI
:Summary: The media verification dialog is improved

:Description:
    Previously, the media verification dialog indicated a good or bad media check result using the
    same sentence, differing only in presence of a single "not". Additionally, the dialog did not
    visually change much upon completion of the check. Consequently, it was not easy to interpret
    the result of the media check, or even see if it was finished.

    The dialog now uses a large icon to signal whether the media is good or not, and while the
    check is running, this icon is absent. As a result, it is now possible to easily tell the state
    of the media check.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/4230
    - https://user-images.githubusercontent.com/15903878/176200267-789a86fe-e874-4b14-aa20-878e63381dca.png
