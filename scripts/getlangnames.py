import sys
sys.path.extend(["..", "../iconvmodule"])
from translate import _
import translate
import language

translate.cat.setunicode(1)

langs = language.InstallTimeLanguage()
for lang in langs.available():
    langs.setRuntimeLanguage(lang)
    print lang, _(lang)

    
