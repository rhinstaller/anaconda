import kudzu
import string
from simpleconfig import SimpleConfigFile

class Keyboard (SimpleConfigFile):
    console2x = {
            "be-latin1"		: ('pc102', 'be'),
            "be2-latin1"	: ('pc102', 'be'),
            "fr-latin0"		: ('pc102', 'fr'),
            "fr-latin1"		: ('pc102', 'fr'),
            "fr-pc"		: ('pc102', 'fr'),
            "fr"		: ('pc102', 'fr'),
            "bg"		: ('pc102', 'bg'),
            "cf"		: ('pc102', 'cf'),
            "cz-lat2-prog" 	: ('pc102', 'cs'),
            "cz-lat2"		: ('pc102', 'cs'),
            "dk-latin1"		: ('pc102', 'dk'),
            "dk"		: ('pc102', 'dk'),
            "es"		: ('pc102', 'es'),
            "fi-latin1"		: ('pc102', 'fi'),
            "fi"		: ('pc102', 'fi'),
            "hu101"		: ('pc102', 'hu'),
            "it-ibm"		: ('pc101', 'it'),
            "it"		: ('pc102', 'it'),
            "it2"		: ('pc102', 'it'),
            "jp106"	        : ('jp106', 'jp'),
            "no-latin1"  	: ('pc102', 'no'),
            "no"		: ('pc102', 'no'),
            "pl"		: ('pc102', 'pl'),
            "pt-latin1"		: ('pc102', 'pt'),
            "ru-cp1251" 	: ('pc102', 'ru'),
            "ru-ms"		: ('microsoft', 'ru'),
            "ru"		: ('pc102', 'ru'),
            "ru1"		: ('pc102', 'ru'),
            "ru2"		: ('pc102', 'ru'),
            "ru_win"		: ('pc105', 'ru'),
            "se-latin1"		: ('pc102', 'se'),
            "us"		: ('pc101', 'us'),
            "de-latin1-nodeadkeys" : ('pc102', 'de'),
            "de-latin1"		: ('pc102', 'de'),
            "de"		: ('pc102', 'de'),
            "fr_CH-latin1" 	: ('pc102', 'fr_CH'),
            "fr_CH"		: ('pc102', 'fr_CH'),
            "hu"		: ('pc102', 'fr_CH'),
            }
    console2xsun = {
	    "sun-pl-altgraph"	: 'pl',
	    "sun-pl"		: 'pl',
	    "sunt4-es"		: 'es',
	    "sunt5-cz-us"	: 'cs',
	    "sunt5-de-latin1"	: 'cs',
	    "sunt5-es"		: 'es',
	    "sunt5-fi-latin1"	: 'fi',
	    "sunt5-fr-latin1"	: 'fr',
	    "sunt5-ru"		: 'ru',
	    "sunt5-uk"		: 'en_US',
	    "sunt5-us-cz"	: 'cs',
	    }

    def __init__ (self):
	self.type = "PC"
	self.model = None
	self.layout = None
        self.info = {}
	list = kudzu.probe(kudzu.CLASS_KEYBOARD, kudzu.BUS_UNSPEC,
			   kudzu.PROBE_ONE)
	if list:
	    (device, module, desc) = list[0]
	    if desc[:14] == 'Serial console':
		self.type = "Serial"
	    elif desc[:8] == 'Sun Type':
		self.type = "Sun"
		if desc[8:1] == '4':
		    self.model = 'type4'
		    desc = desc[10:]
		elif desc[8:6] == '5 Euro':
		    self.model = 'type5_euro'
		    desc = desc[15:]
		elif desc[8:6] == '5 Unix':
		    self.model = 'type5_unix'
		    desc = desc[15:]
		else:
		    self.model = 'type5'
		    desc = desc[10:]
		if desc[:8] == 'Keyboard':
		    self.layout = 'us'
		else:
		    xx = string.split (desc)
		    if xx[0] == 'fr_BE':
			self.layout = 'be'
		    elif xx[0] == 'fr_CA':
			self.layout = 'fr'
		    elif xx[0] == 'nl' or xx[0] == 'ko' or xx[0] == 'tw':
			self.layout = 'us'
		    else:
			self.layout = xx[0]
	if self.type == "Sun":
	    self.info["KEYBOARDTYPE"] = "sun"
	elif self.type != "Serial":
	    self.info["KEYBOARDTYPE"] = "pc"

    def available (self):
	if self.type == "Sun":
	    return [
		"sun-pl-altgraph",
		"sun-pl",
		"sundvorak",
		"sunkeymap",
		"sunt4-es",
		"sunt4-no-latin1.map.gz",
		"sunt5-cz-us",
		"sunt5-de-latin1",
		"sunt5-es",
		"sunt5-fi-latin1",
		"sunt5-fr-latin1",
		"sunt5-ru",
		"sunt5-uk",
		"sunt5-us-cz",
	    ]
	if self.type == "Serial":
	    return [ "us" ]
        return [
            "azerty",
            "be-latin1",
            "be2-latin1",
            "fr-latin0",
            "fr-latin1",
            "fr-pc",
            "fr",
            "wangbe",
            "ANSI-dvorak",
            "dvorak-l",
            "dvorak-r",
            "dvorak",
            "pc-dvorak-latin1",
            "tr_f-latin5",
            "trf",
            "bg",
            "cf",
            "cz-lat2-prog",
            "cz-lat2",
            "defkeymap",
            "defkeymap_V1.0",
            "dk-latin1",
            "dk",
            "emacs",
            "emacs2",
            "es",
            "fi-latin1",
            "fi",
            "gr-pc",
            "gr",
            "hebrew",
            "hu101",
            "is-latin1",
            "it-ibm",
            "it",
            "it2",
            "jp106",
            "la-latin1",
            "lt",
            "lt.l4",
            "nl",
            "no-latin1",
            "no",
            "pc110",
            "pl",
            "pt-latin1",
            "pt-old",
            "ro",
            "ru-cp1251",
            "ru-ms",
            "ru-yawerty",
            "ru",
            "ru1",
            "ru2",
            "ru_win",
            "se-latin1",
            "sk-prog-qwerty",
            "sk-prog",
            "sk-qwerty",
            "tr_q-latin5",
            "tralt",
            "trf",
            "trq",
            "ua",
            "uk",
            "us",
            "croat",
            "cz-us-qwertz",
            "de-latin1-nodeadkeys",
            "de-latin1",
            "de",
            "fr_CH-latin1",
            "fr_CH",
            "hu",
            "sg-latin1-lk450",
            "sg-latin1",
            "sg",
            "sk-prog-qwertz",
            "sk-qwertz",
            "slovene",
            ]

    def set (self, keytable):
	if self.type != "Serial":
	    self.info["KEYTABLE"] = keytable

    def get (self):
        if self.info.has_key ("KEYTABLE"):
            return self.info["KEYTABLE"]
        else:
	    if self.type == "Sun":
		for map in Keyboard.console2xsun.keys():
		    if Keyboard.console2xsun[map] == self.layout:
			return map
		return "sunkeymap"
	    else:
		return "us"

    def getXKB (self):
	if self.type == "PC":
	    if Keyboard.console2x.has_key (self.get ()):
		(model, keylayout) = Keyboard.console2x[self.get ()]
		return ("xfree86", model, keylayout, "", "")
	else:
	    if Keyboard.console2xsun.has_key (self.get ()):
		keylayout = Keyboard.console2xsun[self.get ()]
		return ("sun", self.model, keylayout, "", "")
