#!/usr/bin/python
import sys
import string

sys.path.append ("..")
sys.path.append ("../isys")
sys.path.append ("../kudzu")

from xf86config import XF86Config

xconfig = XF86Config()

pcitable = open ("../kudzu/pcitable", 'r')
lines = pcitable.readlines()
cards = []
for line in lines:
    if line[0] == '#':
        continue
    fields = string.split(line, '\t')
    if len (fields) < 4:
        continue
    card = fields[2]
    if card[1:6] == "Card:":
        cards.append (card[6:-1])

carddb = xconfig.cards()

for card in cards:
    if not carddb.has_key(card):
        print "Card not found:", card
    
