import sys
sys.path.append("..")
from rhpl.translate import _
import rhpl.translate
import language

rhpl.translate.cat.setunicode(1)

langs = language.Language()
names = {}
for k in langs.localeInfo.keys():
    langs.setRuntimeLanguage(k)
    names[langs.localeInfo[k][0]] = _(langs.localeInfo[k][0])

nameList = names.keys()
nameList.sort()

for k in nameList:
    print "%s\t%s" % (k, names[k])
