#
# videocard.py - Install data and probing for video cards
#
# Matt Wilson <msw@redhat.com>
# Brent Fox <bfox@redhat.com>
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import copy
import string
import kudzu
import iutil
import isys
import os

from log import log
from translate import _

Videocard_blacklist = ["Generic VGA compatible",
                       "Generic VGA16",
                       "Generic Mono",
                       "Generic FBDev"]

Video_cardslist = {}

def Video_cardsDBLookup(thecard):
    card = Video_cardslist[thecard]

    return card


class VideoCard:
#
# This class represents the base data about a videocard. These are
# the internal members - PLEASE use methods to access values!
#
#    device   - if framebuffer running on card this is entry in /dev (string)
#    descr    - human readable description (string)
#    server   - X server to use (string)
#    probedcard - value returned for kudzu containing 'Card:........'
#    cardManf - name of manufacturer (string)
#    vidRam   - amount of video ram (in kB) (string)
#    cardData - record from X card database, contains a dictionary of
#               key/values.
#    devID    - ID from ddcprobe (string)
#    fbmodes  - if framebuffer running, video mode in use (string)
#    fbbpp    - if framebuffer running, pixel depth in use (string)
#
# These values will be None if undefined or not applicable.
#

    def __str__ (self):
        return "device: %s\ndescr : %s\nserver: %s\ncardManf: %s\nvidRam: %s\ncarddata: %s\ndevID: %s\nfbmodes: %s\nfbbpp: %s\n" % (self.device, self.descr, self.server, self.cardManf, self.vidRam, self.cardData, self.devID, self.fbmodes, self.fbbpp)


    def __init__ (self):
        self.device = None
        self.probedcard = None
        self.descr  = None
        self.server = None
        self.cardManf = None
        self.vidRam = None
        self.cardData = None
        self.devID = None
        self.fbmodes = None
        self.fbbpp = None
        
    def setDevice(self, device):
        self.device = device

    def setDescription(self, descr):
        self.descr = descr

    def setProbedCard(self, card):
        self.probedcard = card

    def setXServer(self, server):
        self.server = server

    def setVideoRam(self, vidRam):
        self.vidRam = vidRam

    def setCardData(self, card):
        self.cardData = card

    def setDevID(self, devid):
        self.devID = devid

    def setCardManf(self, manf):
        self.cardManf = manf

    def setFBModes(self, fbmodes):
        self.fbmodes = fbmodes

    def setFBBpp(self, bpp):
        self.fbbpp = bpp
        
    def getProbedCard(self):
        return self.probedcard
    
    def getVideoRam(self):
        return self.vidRam

    def getDescription(self):
        return self.descr

    def getDevice(self):
        return self.device

    def getDevID(self):
        return self.devID

    def getXServer(self):
        return self.server

    def getFBBpp(self):
        return self.fbbpp

    def isFrameBuffer(self):
        return 0
        
    def shortDescription(self):
        if self.devID and self.devID != "":
            return self.devID
        else:
            return _("Unable to probe")

    # dontResolve = 1 tells us to not follow 'SEE' records to find
    # true card definition
    def getCardData(self, dontResolve = 0):
        if dontResolve:
            return self.cardData
        else:
            if self.cardData:
                return Video_cardsDBLookup(self.cardData["NAME"])
            else:
                return None

    def canTestSafely(self):
        cardData = self.getCardData()
        if not cardData:
            return 1
        if cardData.has_key("DRIVER"):
            curdriver = cardData["DRIVER"]
            noprobedriverList = ("i810", "tdfx")
            for adriver in noprobedriverList:
                if curdriver == adriver:
                    return 0

        return 1

    def hasFixedMode(self):
        return 0


# fake card entry for frame buffer
class FrameBufferCard(VideoCard):
    def getCardData(self, dontResolve = 0):
        # fake entry for a frame buffer (not in cards db)
        card = {}

# This makes it use the XFree86 4.x fbdev
# also uncomment the code below in getXServer()
        card["DRIVER"] = "fbdev"
#
# This makes is use the XFree 3.x.x fbdev
# also uncomment the code below in getXServer()
#        card["SERVER"] = "FBDev"
         
        card["NAME"] = "VGA VESA Framebuffer"

        return card

    def getXServer(self):
        
# This makes it use the XFree86 4.x fbdev        
# also uncomment the code above in getCardData()
        return "XFree86"
#
# This makes is use the XFree 3.x.x fbdev
# also uncomment the code above in getCardData()
#         return "XF86_FBDev"

    def isFrameBuffer(self):
        return 1

    def hasFixedMode(self):
        return 1

    def FixedMode(self):
        fb = isys.fbinfo()
        if fb:
            (x, y, bpp) = fb
            rc = {}
            rc[str(bpp)] = ["%sx%s" % (x, y)]
            return rc
        return None

# fake card entry for frame buffer
class VGA16Card(VideoCard):
    def getCardData(self, dontResolve = 0):
        # fake entry for a frame buffer (not in cards db)
        card = {}
        card["DRIVER"] = "vga"
        card["NAME"] = "Generic VGA"

        return card

    def getXServer(self):
        return "XFree86"

    def hasFixedMode(self):
        return 1

    def FixedMode(self):
        return { "4" : ["640x480"]}
    
class VideoCardInfo:

#
# This class represents the video cards on the system.
#
# Currently we only care about the primary card on the system.
# This can be found by using the VideoCardInfo::primaryCard() function.
#
# NOTE - X configuration is not represented here. This class is
#        intended only to reprsent the available hardware on the system
#


    def primaryCard(self, useProbed = 0):
        if useProbed:
            if self.orig_videocards and self.orig_primary < len(self.orig_videocards):
                return self.orig_videocards[self.orig_primary]
            else:
                return None
        else:
            if self.videocards and self.primary < len(self.videocards):
                return self.videocards[self.primary]
            else:
                return None

    def possible_ram_sizes(self):
        #--Valid video ram sizes--
        return [256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]

    def index_closest_ram_size(self, detected):
        possram = self.possible_ram_sizes()
        match = -1

        for i in range(0, len(possram)-1):
            if detected <= possram[i]:
                match = i
                break
            elif detected >= possram[i]-64 and detected < possram[i+1]-65:
                match = i
                break

        if match < 0:
            match = len(possram)-1
            
        return match

    def possible_depths(self):
        #--Valid bit depths--
        return ["8", "16", "24", "32"]

    def manufacturerDB(self):
        return ["3DLabs",
                "ABit", "AOpen", "ASUS", "ATI", "Actix", "Ark Logic", "Avance Logic",
                "Compaq", "Canopus", "Cardex", "Chaintech",
                "Chips & Technologies", "Cirrus", "Creative Labs",
                "DFI", "DSV", "DataExpert", "Dell", "Diamond", "Digital",
                "ELSA", "EONtronics", "Epson", "ExpertColor",
                "Gainward", "Genoa", "Guillemot",
                "Hercules",
                "Intel",
                "Jaton",
                "LeadTek",
                "MELCO", "MachSpeed", "Matrox", "Miro",
                "NVIDIA", "NeoMagic", "Number Nine",
                "Oak", "Octek", "Orchid", 
                "Paradise", "PixelView",
                "Quantum",
                "RIVA", "Real3D", "Rendition",
                "S3", "Sharp", "SNI", "SPEA", "STB", "SiS",
                "Sierra", "Sigma", "Silicon Motion", "Soyo", "Spider", "Sun",
                "TechWorks", "Toshiba", "Trident",
                "VideoLogic", "ViewTop", "Voodoo",
                "WD", "Weitek", "WinFast"]     

    def readCardsDB (self):
        # all the straight servers
        for server in [ "3DLabs", "8514", "FBDev", "I128",
                        "Mach8", "Mach32", "Mach64", "Mono",
                        "P9000", "S3", "S3V", "SVGA", "W32", "VGA16" ]:
            Video_cardslist["Generic " + server] = { "SERVER" : server,
                                           "NAME"   : "Generic " + server }

        if not os.access('/usr/X11R6/lib/X11/Cards', os.R_OK):
            return -1
        
        db = open ('/usr/X11R6/lib/X11/Cards')
        lines = db.readlines ()
        db.close ()
        card = {}
        name = None
        for line in lines:
            line = string.strip (line)
            if not line and name:
                Video_cardslist[name] = card
                card = {}
                name = None
                continue
            
            if line and line[0] == '#':
                continue
            
            if len (line) > 4 and line[0:4] == 'NAME':
                name = line[5:]

            if len (line) > 3 and line[0:3] == 'SEE':
                info = string.splitfields (line, ' ')
                seecard = string.joinfields(info[1:], ' ')
                refcard = Video_cardslist[seecard]

                for k in ["CHIPSET", "SERVER", "RAMDAC", "CLOCKCHIP",
                          "DACSPEED", "DRIVER", "UNSUPPORTED", "NOCLOCKPROBE"]:
                    if not card.has_key(k) and refcard.has_key(k):
                        card[k] = refcard[k]

                if refcard.has_key("LINE"):
                    if not card.has_key("LINE"):
                        card["LINE"] = refcard["LINE"]
                    else:
                        card["LINE"] = card["LINE"] + "\n" + refcard["LINE"]
                
            info = string.splitfields (line, ' ')
            if card.has_key (info[0]):
                card[info[0]] = card[info[0]] + '\n' + (string.joinfields (info[1:], ' '))
            else:
                card[info[0]] = string.joinfields (info[1:], ' ')

        return 0

    def cardsDB(self):
        return Video_cardslist

    def __str__(self):
        retstr = "primary: %s\nvidCards: %s\n" % (self.primary, self.videocards)
        if self.primaryCard():
            retstr = retstr + ("Primary Video Card Info:\n%s" % (str(self.primaryCard())))
        return retstr

    def reset(self):
        self.videocards = copy.deepcopy(self.orig_videocards)
        self.primary = self.orig_primary

    def __init__ (self, skipDDCProbe = 0):

        cards = kudzu.probe (kudzu.CLASS_VIDEO,
                             kudzu.BUS_UNSPEC,
                             kudzu.PROBE_ALL);

        # just use first video card we recognize
        # store as a list of class VideoCard
        self.videocards = []
        self.primary = None

        if self.readCardsDB() < 0:
            return None

        for card in cards:
            (device, server, descr) = card

            info = None
            
            if len (server) > 9 and server[0:10] == "Server:Sun" and descr[0:4] == "Sun|":
                server = "Card:Sun " + descr[4:]
            if len (server) > 5 and server[0:5] == "Card:":
                if server[5:] in Video_cardslist.keys():
                    info = Video_cardslist [server[5:]]
                else:
                    info = None
            if len (server) > 7 and server[0:7] == "Server:":
                info = { "NAME" : "Generic " + server[7:],
                         "SERVER" : server[7:] }

            if info:
                vc = VideoCard()
                vc.setProbedCard(server)
                vc.setDevice(device)
                vc.setDescription(descr)
                vc.setCardData (info)
                vc.setDevID (info["NAME"])

                if (vc.getCardData().has_key("DRIVER") and
                    not vc.getCardData().has_key("UNSUPPORTED")):
                    server = "XFree86"
                else:
                    server = "XF86_" + vc.getCardData()["SERVER"]

                vc.setXServer(server)
                self.videocards.append(vc)
                
        if len(self.videocards) == 0:
            # insert a best guess at a card
            vc = VideoCard()
            vc.setDescription(_("Unknown Card"))
            self.videocards.append(vc)
            self.orig_videocards = copy.deepcopy(self.videocards)
            self.primary = 0
            self.orig_primary = self.primary

            return

        # default primary card to be the first card found
        self.primary = 0

        # VESA probe for videoram, etc.
        # for now assume fb corresponds to primary video card
        if not skipDDCProbe:
            try:
                probe = string.split (iutil.execWithCapture ("/usr/sbin/ddcprobe", ['ddcprobe']), '\n')
                for line in probe:
                    if line and line[:9] == "OEM Name:":
                        cardManf = string.strip (line[10:])
                        self.primaryCard().setCardManf(cardManf)
                        self.primaryCard().getCardData()["VENDOR"] = cardManf
                    if line and line[:16] == "Memory installed":
                        memory = string.split (line, '=')
                        self.primaryCard().setVideoRam(string.strip (memory[2][:-2]))
            except:
                log("ddcprobe failed")
                pass

        # try to get frame buffer information if we don't know video ram
        if not self.primaryCard().getVideoRam() and self.primaryCard().getDevice():
            try:
                (vidram, depth, mode, monitor) = isys.fbconProbe("/dev/" + self.primaryCard().getDevice())
                if vidram:
                    self.primaryCard().setVideoRam("%d" % vidram)

                if depth:
                    self.primaryCard().setFBModes({ "%d" % depth : [ mode ] })
                    self.primaryCard().setFBBpp( "%d" % depth )
            except:
                pass

            try:
                if isys.fbinfo() != None:
                    x, y, depth = isys.fbinfo()
                    self.primaryCard().setFBBpp(depth)
            except:
                pass

        # kludge to handle i810 displays which require at least 16 Meg
        if (self.primaryCard().getCardData()).has_key("DRIVER"):
            cardData = self.primaryCard().getCardData()
            if cardData["DRIVER"] == "i810":
                self.primaryCard().setVideoRam("16384")


        # save so we can reset
        self.orig_videocards = copy.deepcopy(self.videocards)
        self.orig_primary = self.primary


#
# XXX needed for kickstart only (via installclass.py::configureX())
#     some useful routines for setting videocard in various ways
#     needs to be ported to new VideoCard object

    # pass videocard object for desired card; this sets card to be
    # primary card
    def setVidcard (self, videocard):
        self.primary = self.videocards.index(videocard)


    # find the appropriate videocard object for the requested card name
    # this will only find the first instance of any card
    def locateVidcardByName (self, card):
        for vc in self.videocards:
            print vc.getDescription()
            if (vc.getDescription() == card):
                return vc
        raise RuntimeError, "Could not find valid video card driver"

    # find the appropriate videocard object for the requested server name
    # this will only find the first instance of any card
    def locateVidcardByServer (self, server):
        for vc in self.videocards:
            if (vc.getXServer() == server):
                return vc
        raise RuntimeError, "Could not find valid video card driver."
