#!/usr/bin/python
import sys
import string

def usage():
    print "Usage: checkcards.py [pcitable] [Cards]"

if len(sys.argv) < 2:
    usage ()
    sys.exit (1)

pcifile = sys.argv[1]
cardsfile = sys.argv[2]

def getcards (cardsfile):
    cards = {}
    db = open (cardsfile)
    lines = db.readlines ()
    db.close ()
    card = {}
    name = None
    for line in lines:
        line = string.strip (line)
        if not line and name:
            cards[name] = card
            card = {}
            name = None
            continue

        if line and line[0] == '#':
            continue

        if len (line) > 4 and line[0:4] == 'NAME':
            name = line[5:]

        info = string.splitfields (line, ' ')
        if card.has_key (info[0]):
            card[info[0]] = card[info[0]] + '\n' + (string.joinfields (info[1:], ' '))
        else:
            card[info[0]] = string.joinfields (info[1:], ' ')

    return cards

pcitable = open (pcifile, 'r')
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

carddb = getcards (cardsfile)

for card in cards:
    if not carddb.has_key(card):
        print "*** pcitable error *** Card not found:", card
