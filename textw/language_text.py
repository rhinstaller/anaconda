#
# language_text.py: text mode language selection dialog
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import isys
import iutil
from snack import *
from constants_text import *
from flags import flags

from rhpl.log import *
from rhpl.translate import _

class LanguageWindow:
    def __call__(self, screen, textInterface, instLanguage):
        languages = instLanguage.available ()

        haveKon = os.access ("/sbin/continue", os.X_OK)

        current = instLanguage.getCurrent()

        height = min((screen.height - 16, len(languages)))
	buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON]

        translated = []
        for lang in languages:
            translated.append (_(lang))
        (button, choice) = \
            ListboxChoiceWindow(screen, _("Language Selection"),
			_("What language would you like to use during the "
			  "installation process?"), translated, 
			buttons, width = 30, default = _(current), scroll = 1,
                                height = height, help = "lang")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        choice = languages[choice]
        
        if (((not haveKon and instLanguage.getFontFile(choice) == "Kon") or
            instLanguage.getFontFile(choice) == "None") and
            (iutil.getArch() != "s390")):
            ButtonChoiceWindow(screen, "Language Unavailable",
                               "%s display is unavailable in text mode.  The "
                               "installation will continue in English." % (choice,),
                               buttons=[TEXT_OK_BUTTON])
            instLanguage.setRuntimeDefaults(choice)
            return INSTALL_OK
            
        if (flags.setupFilesystems and
            instLanguage.getFontFile(choice) == "Kon"
            and not isys.isPsudoTTY(0)):
            # we're not running KON yet, lets fire it up
            os.environ["ANACONDAARGS"] = (os.environ["ANACONDAARGS"] +
                                          " --lang ja_JP.eucJP")
            os.environ["TERM"] = "kon"
            os.environ["LANG"] = "ja_JP.eucJP"
            os.environ["LC_ALL"] = "ja_JP.eucJP"
            os.environ["LC_NUMERIC"] = "C"
            if iutil.getArch() != "s390":
                if os.access("/tmp/updates/anaconda", os.X_OK):
                    prog = "/tmp/updates/anaconda"
                else:
                    prog = "/usr/bin/anaconda"
                args = [ "kon", "-e", prog ]
                screen.finish()
                os.execv ("/sbin/loader", args)

	instLanguage.setRuntimeLanguage(choice)
                
	if not flags.serial:
	    map = instLanguage.getFontMap(choice)
	    font = instLanguage.getFontFile(choice)
	    if map != "None":
		if os.access("/bin/consolechars", os.X_OK):
		    iutil.execWithRedirect ("/bin/consolechars",
					["/bin/consolechars", "-f", font, "-m", map])
		else:
		    try:
			isys.loadFont(map)
		    except SystemError, (errno, msg):
			log("Could not load font %s: %s" % (font, msg))
	    elif os.access("/bin/consolechars", os.X_OK):
		# test
		iutil.execWithRedirect ("/bin/consolechars", 
			["/bin/consolechars", "-d", "-m", "iso01"])

	textInterface.drawFrame()
	    
        return INSTALL_OK

class LanguageSupportWindow:
    def __call__(self, screen, language):

	# should already be sorted
        ct = CheckboxTree(height = 8, scroll = 1)

        for lang in language.getAllSupported():
	    ct.append(lang, lang, 0)

	for lang in language.getSupported ():
	    ct.setEntryValue(lang, 1)

	current = language.getDefault()
	ct.setCurrent(current)
	ct.setEntryValue(current, 1)

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, (_("Select All"), "all"), (_("Reset"), "reset"), TEXT_BACK_BUTTON))

        message = (_("Choose additional languages that you would like to use "
                     "on this system:"))
        tb = TextboxReflowed(50, message)

        g = GridFormHelp (screen, _("Language Support"), "langsupport", 1, 4)
        
        g.add (tb, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        g.add (ct, 0, 1, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

        while 1:
            result = g.run()

            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if rc == "all":
                for lang in language.getAllSupported():
                    ct.setEntryValue(lang, 1)

            if rc == "reset":
                for lang in language.getAllSupported():
                    if lang == current:
                        ct.setEntryValue(lang, 1)
                    else:
                        ct.setEntryValue(lang, 0)

            if rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                # --If they selected all langs, then set language.setSupported to 
                # None.  This installs all langs

                if ct.getSelection() == []:
                    ButtonChoiceWindow(screen, _("Invalid Choice"),
                                       _("You must select at least one language to install."),
                                       buttons = [ TEXT_OK_BUTTON ], width = 40)

                else:
                    # we may need to reset the default language
                    language.setSupported (ct.getSelection())
                    default = language.getDefault()
                    if default not in ct.getSelection():
                        language.setDefault(None)
                    screen.popWindow()
                    return INSTALL_OK


class LanguageDefaultWindow:
    def __call__(self,screen, language):
        langs = language.getSupported ()
	current = language.getDefault()

        if not langs or len(langs) <= 1:
	    language.setDefault(current)
            return INSTALL_NOOP

	langs.sort()

        height = min((screen.height - 16, len(langs)))
        
        buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON]

        (button, choice) = ListboxChoiceWindow(screen, _("Default Language"),
			_("Choose the default language for this system: "), langs, 
			buttons, width = 30, default = current, scroll = 1,
                                               height = height, help = "langdefault")

	if (button == TEXT_BACK_CHECK):
            return INSTALL_BACK

        language.setDefault (langs[choice])
        return INSTALL_OK

