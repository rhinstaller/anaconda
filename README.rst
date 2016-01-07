translation-canary
-------------

Translations can crash your program. Creating software for a wide audience
means sending your strings away for translation, and giving up control of your
strings means that strings with extralinguistic content can come back broken.
No one is likely to even realize it until someone fires up your program in
Hungarian and it crashes because Gtk bombed out on some busted markup, and the
Hungarian speaker is sad, and you are sad, and everything is just the absolute
worst.

This is the canary in the translation coalmine.

There are two parts to this project:

translatable:
  This contains checks on the strings to be submitted for translation. This
  ensures that the content of the original strings marked for translation are
  suitable for translation. These tests are run on the POT file before
  uploading the POT or the updated PO files to the translators.

translated:
  This contains checks on the strings returned from the translators. This
  ensures that the content of the translated strings won't break anything.
  These tests are run on the source directory before creating a release.

Both translatable and translated are run by running the module
(e.g., `python3 -m translation_canary.translatable`) with the input file(s) as
the argument.

In addition to the python modules, this project contains xgettext_werror.sh, a
wrapper for xgettext that treats warnings as errors.  xgettext will print
warnings as it extracts translatable strings from source files, and these
warnings should be addressed instead of silently ignored as they scroll by in
the build output. To use the script in a package that uses the gettext template
files from autopoint or gettextize, set XGETTEXT=/path/to/xgettext_werror.sh in
Makevars.
