#
# xconfig_text.py: text mode X Windows System setup dialogs
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

from monitor import isValidSyncRange
from videocard import Videocard_blacklist
from constants_text import *
from snack import *
from translate import _

class XCustomWindow:

    def depthchangeCB(self, screen):
        (button, result) = ListboxChoiceWindow(screen, _("Color Depth"),
                            _("Please select the color depth you "
                            "would like to use:") , self.available_depths,
                            [ TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON],
                            scroll = 0, height = 3, help = "colordepthsel",
                            default = self.bit_depth.index(self.selectedDepth))

        if button != TEXT_CANCEL_CHECK:
            self.selectedDepth = self.bit_depth[result]
            self.available_res = self.available_res_by_depth[self.selectedDepth]
            if not self.selectedRes in self.available_res:
                self.selectedRes = self.available_res[-1]

    def reschangeCB(self, screen):
        try:
            sel = self.available_res.index(self.selectedRes)
        except:
            sel = len(self.available_res)
            
        (button, result) = ListboxChoiceWindow(screen, _("Resolution"),
                            _("Please select the resolution you "
                            "would like to use:") , self.available_res,
                            [ TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON],
                            scroll = (len(self.available_res) > 7), height = 7, help = "resdepthsel",
                            default = sel)

        if button != TEXT_CANCEL_CHECK:
            self.selectedRes = self.available_res[result]
        
    def testCB(self, screen):
        newmodes = {}
        newmodes[self.selectedDepth] = []
        newmodes[self.selectedDepth].append (self.selectedRes)

        manmodes = self.xconfig.getManualModes()
        self.xconfig.setManualModes(newmodes)

        try:
            self.xconfig.test (root="/mnt/sysimage")
        except RuntimeError:
            ### test failed window
            pass

        self.xconfig.setManualModes(manmodes)
        
    def loginCB(self, widget):
        if widget == self.graphrb:
            self.selectedRunLevel = 5
        elif widget == self.textrb:
            self.selectedRunLevel = 3
        else:
            print "Invalid widget in xconfig_text::loginCB"
        

    def desktopCB(self, widget):
        if widget == self.gnomerb:
            self.selectedDesktop = "GNOME"
        elif widget == self.kderb:
            self.selectedDesktop = "KDE"
        else:
            print "Invalid widget in xconfig_text::desktopCB"


    def __call__(self, screen, xconfig, monitor, videocard, desktop, comps):

        def numCompare (first, second):
            first = string.atoi (first)
            second = string.atoi (second)
            if first > second:
                return 1
            elif first < second:
                return -1
            return 0

        self.xconfig = xconfig

        depth_list = [(_("256 Colors (8 Bit)")), (_("High Color (16 Bit)")), (_("True Color (24 Bit)"))]
        self.bit_depth = ["8", "16", "32"]
        self.res_list = ["640x480", "800x600", "1024x768", "1152x864",
                         "1280x1024", "1400x1050", "1600x1200"]

        self.available_res_by_depth = self.xconfig.availableModes()
        availableDepths = []
        for adepth in self.available_res_by_depth.keys():
            if len(self.available_res_by_depth[adepth]) > 0:
                availableDepths.append(adepth)
        availableDepths.sort(numCompare)

        self.available_depths = []
        for i in availableDepths:
               self.available_depths.append(depth_list[self.bit_depth.index(i)])
        manualmodes = self.xconfig.getManualModes()
        if manualmodes:
            self.selectedDepth = manualmodes.keys()[0]
            self.selectedRes = manualmodes[self.selectedDepth][0]
        else:
            self.selectedDepth = None
            self.selectedRes = None

        # if selected depth not acceptable then force it to be at least 8bpp
        if self.selectedDepth and int(self.selectedDepth) < 8:
            self.selectedDepth = "8"

        if not self.selectedDepth or not self.selectedRes:
            if len(self.available_res_by_depth) == 1:
                self.available_res = self.available_res_by_depth["8"]
                self.selectedDepth = "8"
                self.selectedRes = self.available_res[0]
            elif len(self.available_res_by_depth) >= 2:
                #--If they can do 16 bit color, default to 16 bit at 1024x768
                self.selectedDepth = "16"
            
                self.available_res = self.available_res_by_depth["16"]

                if "1024x768" in self.available_res_by_depth["16"]:
                    self.selectedRes = "1024x768"
                elif "800x600" in self.available_res_by_depth["16"]:
                    self.selectedRes = "800x600"
                else:
                    self.selectedRes = "640x480"
        else:
            self.available_res = self.available_res_by_depth[self.selectedDepth]
        #--If both KDE and GNOME are selected
        if comps:
            gnomeSelected = (comps.packages.has_key('gnome-core')
                             and comps.packages['gnome-core'].selected)
            kdeSelected = (comps.packages.has_key('kdebase')
                           and comps.packages['kdebase'].selected)
        else:
            gnomeSelected = 0
            kdeSelected = 0

        self.selectedDesktop = desktop.getDefaultDesktop()
        self.selectedRunLevel = desktop.getDefaultRunLevel()

        while 1:
            bb = ButtonBar (screen, (TEXT_OK_BUTTON, (_("Test"), "test"),
                                     TEXT_BACK_BUTTON))

            toplevel = GridFormHelp (screen, _("X Customization"),
                                     "custom", 1, 5)

            text = _("Select the color depth and video mode you want to "
                     "use for your system. "
                     "Use the '%s' button to test the video mode."
                     % (_("Test")))

            customgrid = Grid(3,2)
            label = Label(_("Color Depth:"))
            customgrid.setField(label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
            field = Textbox(20, 1, depth_list[self.bit_depth.index(self.selectedDepth)])
            customgrid.setField(field, 1, 0, (0, 0, 0, 1), anchorLeft = 1)
            depthchangebutton = CompactButton(_("Change"))
            customgrid.setField (depthchangebutton, 2, 0, (0, 0, 0, 1),
                                 anchorLeft = 1)
            label = Label(_("Resolution:"))
            customgrid.setField(label, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
            field = Textbox(14, 1, self.selectedRes)
            customgrid.setField(field, 1, 1, (0, 0, 0, 1), anchorLeft = 1)
            reschangebutton = CompactButton(_("Change"))
            customgrid.setField (reschangebutton, 2, 1, (0, 0, 0, 1),
                                 anchorLeft = 1)

            if gnomeSelected or kdeSelected:
                desktopgrid = Grid(3,2)
                label = Label(_("Default Desktop:"))
                desktopgrid.setField(label, 0, 1, (0, 0, 0, 1), anchorLeft = 1)

                if gnomeSelected and kdeSelected:
                    self.gnomerb = SingleRadioButton(_("GNOME"), None,
                                                     self.selectedDesktop == "GNOME")
                    self.kderb = SingleRadioButton(_("KDE"), self.gnomerb,
                                                   self.selectedDesktop == "KDE")
                    self.gnomerb.setCallback(self.desktopCB, self.gnomerb)
                    self.kderb.setCallback(self.desktopCB, self.kderb)
                    desktopgrid.setField(self.gnomerb, 1, 1, (0, 0, 0, 1), anchorLeft = 1)
                    desktopgrid.setField(self.kderb, 2, 1, (0, 0, 0, 1), anchorLeft = 1)
                elif gnomeSelected:
                    desktopgrid.setField(Textbox(10, 1, _("GNOME")), 1, 1, (0, 0, 0, 1), anchorLeft = 1)
                elif kdeSelected:
                    desktopgrid.setField(Textbox(10, 1, _("KDE")), 1, 1, (0, 0, 0, 1), anchorLeft = 1)
            else:
                desktopgrid = None

            runlevelgrid = Grid(3,2)
            label = Label(_("Default Login:"))
            runlevelgrid.setField(label, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
            self.graphrb = SingleRadioButton(_("Graphical"), None,
                                             (self.selectedRunLevel == 5))
            self.textrb = SingleRadioButton(_("Text"), self.graphrb,
                                            (self.selectedRunLevel == 3))
            self.graphrb.setCallback(self.loginCB, self.graphrb)
            self.textrb.setCallback(self.loginCB, self.textrb)
            runlevelgrid.setField(self.graphrb, 1, 1, (0, 0, 0, 1),
                                  anchorLeft = 1)
            runlevelgrid.setField(self.textrb, 2, 1, (0, 0, 0, 1),
                                  anchorLeft = 1)

            toplevel.add(TextboxReflowed(55, text), 0, 0, (0, 0, 0, 1))
            toplevel.add(customgrid, 0, 1, (0, 0, 0, 0), growx = 1)
            if desktopgrid:
                toplevel.add(desktopgrid, 0, 2, (0, 0, 0, 0), growx = 1)
            toplevel.add(runlevelgrid, 0, 3, (0, 0, 0, 0), growx = 1)
            toplevel.add(bb, 0, 4, (0, 0, 0, 0), growx = 1)

	    result = toplevel.run ()
	    rc = bb.buttonPressed (result)

	    if rc == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK
            elif rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                screen.popWindow()
                break
            elif rc == "test":
                self.testCB(screen)
            elif result == depthchangebutton:
                self.depthchangeCB(screen)
            elif result == reschangebutton:
                self.reschangeCB(screen)

            screen.popWindow()

        # store results
        newmodes = {}
        newmodes[self.selectedDepth] = []
        newmodes[self.selectedDepth].append (self.selectedRes)
        self.xconfig.setManualModes(newmodes)

        desktop.setDefaultDesktop (self.selectedDesktop)
        desktop.setDefaultRunLevel(self.selectedRunLevel)
        
        return INSTALL_OK
 
class MonitorWindow:
    def monchangeCB(self, screen):
        (button, result) = ListboxChoiceWindow(screen, _("Monitor"),
                            _("Please select the monitor attached to your "
                            "system.") , self.monitorsnames,
                            [ TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON],
                            scroll = 1, height = 7, help = "monitor",
                            default = self.selectedMonitor)

        if button != TEXT_CANCEL_CHECK:
            self.selectedMonitor = result
            selMonitorName = self.monitorsnames[self.selectedMonitor]
            selMonitor = self.monitor.lookupMonitor(selMonitorName)

            self.hsync = selMonitor[3]
            self.vsync = selMonitor[2]

    def syncchangeCB(self, screen):
        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON))

        toplevel = GridFormHelp(screen, _("Monitor Sync Rates"),
                                "monitorsyncrates", 1, 5)

        syncgrid = Grid(2,2)

        text = _("Please enter the sync rates for your monitor. \n\nNOTE - "
                 "it is not usually necessary to edit sync rates manually, "
                 "and care should be taken to "
                 "make sure the values entered are accurate.")

        label = Label(_("HSync Rate: "))
        syncgrid.setField(label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        hentry = Entry(30)
        hentry.set(self.hsync)
        syncgrid.setField(hentry, 1, 0, (0, 0, 0, 1), anchorLeft = 1)
        label = Label(_("VSync Rate: "))
        syncgrid.setField(label, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
        ventry = Entry(30)
        ventry.set(self.vsync)
        syncgrid.setField(ventry, 1, 1, (0, 0, 0, 1), anchorLeft = 1)

        toplevel.add(TextboxReflowed(55, text), 0, 0, (0, 0, 0, 0))
        toplevel.add(syncgrid, 0, 1, (0, 1, 0, 1), growx = 1)
        toplevel.add(bb, 0, 3, (0, 0, 0, 0), growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)

	    if rc == TEXT_CANCEL_CHECK:
		screen.popWindow()
		return
            elif rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                if hentry.value() and ventry.value():
                    hval = hentry.value()
                    vval = ventry.value()
                    hgood = isValidSyncRange(hval)
                    vgood = isValidSyncRange(vval)
                    if not hgood:
                        badtitle = _("horizontal")
                        badone = hval
                    elif not vgood:
                        badtitle = _("vertical")
                        badone = vval
                    
                    if isValidSyncRange(hval) and isValidSyncRange(vval):
                        self.hsync = hval
                        self.vsync = vval
                        screen.popWindow()
                        return
                    else:
                        ButtonChoiceWindow(screen, _("Invalid Sync Rates"),
                         _("The %s sync rate is invalid:\n\n      %s\n\n"
                           "A valid sync rate can be of the form:\n\n"
                           "      31.5                   a single number\n"
                           "    50.1-90.2                a range of numbers\n"
                           "31.5,35.0,39.3-40.0          a list of numbers/ranges\n") % (badtitle, badone),
                           buttons = [ TEXT_OK_BUTTON ], width = 45)

    def resetCB(self, screen):
        self.hsync = self.orig_hsync
        self.vsync = self.orig_vsync
        self.selectedMonitor = self.origMonitor
        
    def __call__(self, screen, xconfig, monitor):

        self.xconfig = xconfig
        self.monitor = monitor

        self.monDB = self.monitor.monitorsDB()
        self.monitorslist = {}
        for man in self.monDB.keys():
            for mon in self.monDB[man]:
                self.monitorslist[mon[0]] = mon
        self.monitorsnames = self.monitorslist.keys()
        self.monitorsnames.sort()

        try:
            self.origMonitor = self.monitorsnames.index(self.monitor.getMonitorID(useProbed=1))
        except:
            self.origMonitor = 0

        try:
            self.selectedMonitor = self.monitorsnames.index(self.monitor.getMonitorID())
        except:
            try:
                self.selectedMonitor = self.monitorsnames.index('Generic Standard VGA, 640x480 @ 60 Hz')
            except:
                raise RuntimeError, "Could not match monitor %s" % (self.monitor.getMonitorID())


        self.hsync = self.monitor.getMonitorHorizSync()
        self.orig_hsync = self.monitor.getMonitorHorizSync(useProbed=1)
        self.vsync = self.monitor.getMonitorVertSync()
        self.orig_vsync = self.monitor.getMonitorVertSync(useProbed=1)

	while 1:
            selMonitorName = self.monitorsnames[self.selectedMonitor]
            selMonitor = self.monitor.lookupMonitor(selMonitorName)
            
            bb = ButtonBar (screen, (TEXT_OK_BUTTON, (_("Default"), "default"),
                                     TEXT_BACK_BUTTON))

            toplevel = GridFormHelp (screen, _("Monitor Configuration"),
                                     "monitor", 1, 5)

            text = _("Select the monitor for your system.  Use the '%s' "
                     "button to reset to the probed values.") % (_("Default"))

            videogrid = Grid(3, 3)
            label = Label(_("Monitor:"))
            videogrid.setField (label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
            monlabel = Textbox(20, 1, (selMonitor[0]))
            videogrid.setField (monlabel, 1, 0, (0, 0, 0, 1), anchorLeft = 1)
            monchangebutton = CompactButton(_("Change"))
            videogrid.setField (monchangebutton, 2, 0, (0, 0, 0, 1), anchorLeft = 1)
        
            label = Label(_("HSync Rate:"))
            videogrid.setField (label, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
            if self.hsync:
                synctext = self.hsync
            else:
                synctext = "Unknown"
            synclabel = Textbox(20, 1, synctext)
            videogrid.setField (synclabel, 1, 1, (0, 0, 0, 0), anchorLeft = 1)
            syncchangebutton = CompactButton(_("Change"))
            videogrid.setField (syncchangebutton, 2, 1, (0, 0, 0, 0), anchorLeft = 1)
            label = Label(_("VSync Rate:"))
            videogrid.setField (label, 0, 2, (0, 0, 0, 0), anchorLeft = 1)
            if self.vsync:
                synctext = self.vsync
            else:
                synctext = "Unknown"
            synclabel = Textbox(20, 1, synctext)
            videogrid.setField (synclabel, 1, 2, (0, 0, 0, 0), anchorLeft = 1)

            toplevel.add(TextboxReflowed(60, text), 0, 0, (0, 0, 0, 0))
            toplevel.add(videogrid, 0, 1, (0, 1, 0, 1), growx = 1)
            toplevel.add(bb, 0, 4, (0, 0, 0, 0), growx = 1)

	    result = toplevel.run ()
	    rc = bb.buttonPressed (result)

	    if rc == TEXT_BACK_CHECK:
                # XXX - dont let them go back to make boot disk screen
                ButtonChoiceWindow(screen, _("Error"),
                                   _("You cannot go back from this "
                                     "step."),
                           buttons = [ TEXT_OK_BUTTON ])
            elif rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                screen.popWindow()
                break
            elif rc == "default":
                self.resetCB(screen)
            elif result == monchangebutton:
                self.monchangeCB(screen)
            elif result == syncchangebutton:
                self.syncchangeCB(screen)
            
            screen.popWindow()

        # store results
        selMonitorName = self.monitorsnames[self.selectedMonitor]
        selMonitor = self.monitor.lookupMonitor(selMonitorName)

        self.monitor.setSpecs(selMonitor[3], 
                              selMonitor[2],
                              id=selMonitor[0],
                              name=selMonitor[0])
        
        
        return INSTALL_OK

class XConfigWindowCard:

    # try to match card currently selected, then a generic VGA if card not
    # found, then just first in list
    def findCardInList(self, current_cardsel):
        index = 0
        backupindex = None
        for card in self.cardslist:
            if card == current_cardsel:
                self.curcardindex = index
                break
            elif card == "Generic VGA compatible":
                backupindex = index
            index = index + 1

        if index < len(self.cardslist):
            return index
        elif backupindex:
            return backupindex
        else:
            return 0


    def cardchangeCB(self, screen):
        
        while 1:
            (button, result) = ListboxChoiceWindow(screen, _("Video Card"),
                          _("Please select the video card present in your "
                            "system.  Choose '%s' to reset the selection to "
                            "the card the installer detected in your "
                            "system.") % (_("Default")) , self.cardslist,
                          [ TEXT_OK_BUTTON, (_("Default"), "default")],
                          scroll = 1, height = 7, help = "videocardsel",
                          default = self.selectedCard)

            if button == 'default':
                self.selectedCard = self.origCard
            else:
                break
            
        self.selectedCard = result

    def ramchangeCB(self, screen):

        while 1:
            (button, result) = ListboxChoiceWindow(screen, _("Video RAM"),
                          _("Please select the amount of video RAM present "
                            "on your video card. "
                            "Choose '%s' to reset the selection to "
                            "the amount the installer detected on your "
                            "card.") % (_("Default")) , self.ramlist,
                          [ TEXT_OK_BUTTON, (_("Default"), "default")],
                          scroll = 1, height = 7, help = "videocardsel",
                          default = self.selectedRam)

            if button == 'default':
                self.selectedRam = self.origRam
            else:
                break
            
        self.selectedRam = result
            

    
    def __call__(self, screen, dispatch, xconfig, videocard, intf):
        
        self.dispatch = dispatch
        self.videocard = videocard
        self.xconfig = xconfig

        self.xconfig.filterModesByMemory ()

        # setup database and list of possible cards
        self.cards = self.videocard.cardsDB()
        self.cardslist = self.cards.keys()
        self.cardslist.sort()
        for card in Videocard_blacklist:
            try:
                self.cardslist.remove(card)
            except:
                pass

        self.ramlist = []
        for ram in self.videocard.possible_ram_sizes():
            self.ramlist.append(str(ram))

        carddata = self.videocard.primaryCard().getCardData(dontResolve=1)
        if carddata:
            self.selectedCard = self.findCardInList(carddata["NAME"])
        else:
            self.selectedCard = None

        carddata = self.videocard.primaryCard(useProbed=1).getCardData(dontResolve=1)
        if carddata:
            self.origCard = self.findCardInList(carddata["NAME"])
        else:
            self.origCard = None

        try:
            vidRam = string.atoi(self.videocard.primaryCard().getVideoRam())
        except:
            vidRam = 1024

        count = 0
        for size in self.videocard.possible_ram_sizes():
            #--Cards such as Mach64 and ATI Rage Mobility report 64k less ram
            #  than it should
            small = size - 64
            if size == vidRam or small == vidRam:
                break
            count = count + 1

        print vidRam, count

        self.selectedRam = count

        try:
            vidRam = string.atoi(self.videocard.primaryCard(useProbed=1).getVideoRam())
        except:
            vidRam = 1024

        count = 0
        for size in self.videocard.possible_ram_sizes():
            #--Cards such as Mach64 and ATI Rage Mobility report 64k less ram
            #  than it should
            small = size - 64
            if size == vidRam or small == vidRam:
                break
            count = count + 1

        self.origRam = count
            
        skipx = 0
	while 1:
            bb = ButtonBar (screen, (TEXT_OK_BUTTON,
                                     (_("Skip X Configuration"), "skipx"),
                                     TEXT_BACK_BUTTON))

            toplevel = GridFormHelp (screen, _("Video Card Configuration"),
                                     "videocard", 1, 5)

            text = _("Select the video card and video RAM for your system.")

            videogrid = Grid(3, 2)
            label = Label(_("Video Card:"))
            videogrid.setField (label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
            if self.selectedCard != None:
                cardlbl =  self.cardslist[self.selectedCard]
            else:
                cardlbl = _("Unknown card")
                
            cardlabel = Textbox(28, 1, cardlbl)
                
            videogrid.setField (cardlabel, 1, 0, (0, 0, 0, 1), anchorLeft = 1)
            cardchangebutton = CompactButton(_("Change"))
            videogrid.setField (cardchangebutton, 2, 0, (0, 0, 0, 1), anchorLeft = 1)
        
            label = Label(_("Video RAM:"))
            videogrid.setField (label, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
            ramlabel = Textbox(12, 1, self.ramlist[self.selectedRam])
            videogrid.setField (ramlabel, 1, 1, (0, 0, 0, 0), anchorLeft = 1)
            ramchangebutton = CompactButton(_("Change"))
            videogrid.setField (ramchangebutton, 2, 1, (0, 0, 0, 0), anchorLeft = 1)
            toplevel.add(TextboxReflowed(60, text), 0, 0, (0, 0, 0, 0))
            toplevel.add(videogrid, 0, 1, (0, 1, 0, 1), growx = 1)
            toplevel.add(bb, 0, 4, (0, 0, 0, 0), growx = 1)

	    result = toplevel.run ()
	    rc = bb.buttonPressed (result)

	    if rc == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK
            elif rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
                # we're done
                # see if they have not specified card yet
                if self.selectedCard == None:
                    intf.messageWindow(_("Unspecified video card"),
                                    _("You need to pick a video card before "
                                      "X configuration can continue.  If you "
                                      "want to skip X configuration entirely "
                                  "choose the 'Skip X Configuration' button."))
                    continue
                break
            elif rc == "skipx":
                skipx = 1
                break
            elif result == cardchangebutton:
                self.cardchangeCB(screen)
            elif result == ramchangebutton:
                self.ramchangeCB(screen)
            
            screen.popWindow()

        screen.popWindow()
        if skipx == 1:
            self.dispatch.skipStep("monitor")
            self.dispatch.skipStep("xcustom")
            self.dispatch.skipStep("writexconfig")
            self.xconfig.skipx = 1
            return INSTALL_OK
        else:
            self.dispatch.skipStep("monitor", skip = 0)
            self.dispatch.skipStep("xcustom", skip = 0)
            self.dispatch.skipStep("writexconfig", skip = 0)
            self.xconfig.skipx = 0

        # store selected videocard
        selection = self.cards[self.cardslist[self.selectedCard]]
        primary_card = self.videocard.primaryCard()
        primary_card.setCardData(selection)
        primary_card.setDevID (selection["NAME"])
        primary_card.setDescription (selection["NAME"])

        # pull out resolved version of card data
        card_data = primary_card.getCardData()
        if (card_data.has_key("DRIVER") and
            not card_data.has_key("UNSUPPORTED")):
            server = "XFree86"
        else:
            server = "XF86_" + card_data["SERVER"]

        primary_card.setXServer(server)

        # store selected ram
        vidram = self.videocard.possible_ram_sizes()[self.selectedRam]
        self.videocard.primaryCard().setVideoRam(str(vidram))
        self.xconfig.filterModesByMemory ()

        return INSTALL_OK
