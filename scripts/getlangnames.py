import sys
sys.path.append("..")
from rhpl.translate import _
import rhpl.translate
import language

rhpl.translate.cat.setunicode(1)

langs = language.InstallTimeLanguage()
for lang in langs.available():
    langs.setRuntimeLanguage(lang)
    print lang, _(lang)

    
