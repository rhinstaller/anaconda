import sys
from rhpl.translate import _
import rhpl.translate
import language

langs = language.InstallTimeLanguage()
for lang in langs.available():
    langs.setRuntimeLanguage(lang)
    print lang, _(lang)

    
