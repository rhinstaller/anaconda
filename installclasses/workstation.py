from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil
from autopart import getAutopartitionBoot, autoCreatePartitionRequests
from fsset import *

class InstallClass(BaseInstallClass):
    name = N_("Workstation")
    pixmap = "workstation.png"
    description = N_("For systems intended for graphical desktop use using "
		     "the GNOME or KDE desktop environments.")

    sortPriority = 1

    # FIXME: THIS IS A HORRIBLE HACK AND MUST GO AWAY
    def selectDependentHiddenGroups(self, id):
        BaseInstallClass.selectDependentHiddenGroups(self, id)
        if id.comps["GNOME Desktop Environment"].isSelected():
            log("GNOME was selected, adding necessary components")
            id.comps["GNOME Office/Productivity Software"].select()
            id.comps["GNOME Multimedia Software"].select()
            id.comps["GNOME Messaging and Web Tools"].select()            
            if id.comps["Games and Entertainment"].isSelected():
                id.comps["GNOME Games and Entertainment"].select()
            if id.comps["Software Development"].isSelected():
                id.comps["GNOME Software Development"].select()

        if id.comps["KDE Desktop Environment"].isSelected():
            log("KDE was selected, adding necessary components")
            id.comps["KDE Office/Productivity Software"].select()
            id.comps["KDE Multimedia Software"].select()
            id.comps["KDE Messaging and Web Tools"].select()            
            if id.comps["Games and Entertainment"].isSelected():
                id.comps["KDE Games and Entertainment"].select()
            if id.comps["Software Development"].isSelected():
                id.comps["KDE Software Development"].select()

        if id.comps["Games and Entertainment"].isSelected():
            id.comps["X Based Games and Entertainment"].select()
        if id.comps["Software Development"].isSelected():
            id.comps["X Software Development"].select()

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
	dispatch.skipStep("authentication")

        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
#	self.showGroups(comps, [ "KDE Desktop Environment",
#                                 ("GNOME Desktop Environment", 1),
#                                 "Software Development",
#                                 "Games and Entertainment" ] )
        comps["Workstation Common"].select()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

        autorequests = [ ("/", None, 1100, None, 1, 1) ]

        bootreq = getAutopartitionBoot()
        if bootreq:
            autorequests.append(bootreq)

        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append((None, "swap", minswap, maxswap, 1, 1))

        id.partitions.autoClearPartType = CLEARPART_TYPE_LINUX
        id.partitions.autoClearPartDrives = None
        id.partitions.autoPartitionRequests = autoCreatePartitionRequests(autorequests)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
