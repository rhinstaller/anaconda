from installclass import BaseInstallClass
from translate import N_
import os
import iutil
from partitioning import *
from fsset import *
from autopart import CLEARPART_TYPE_LINUX
from autopart import CLEARPART_TYPE_ALL
from autopart import CLEARPART_TYPE_NONE

class InstallClass(BaseInstallClass):
    name = N_("Workstation")
    pixmap = "workstation.png"

    sortPriority = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);

	if self.skipLilo:
	    dispatch.skipStep("bootloader")

	dispatch.skipStep("authentication")
	dispatch.skipStep("bootdisk", skip = 0)

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, [ "KDE", ("GNOME", 1), "Games" ] )

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
	self.setHostname(id, "localhost.localdomain")

        rootrequest = PartitionSpec(fileSystemTypeGet("ext2"),
                                    mountpoint = "/",
                                    size = 800,
                                    grow = 1,
                                    requesttype = REQUEST_NEW,
                                    format = 1)

        bootrequest = PartitionSpec(fileSystemTypeGet("ext2"),
                                    mountpoint = "/boot",
                                    size = 100,
                                    grow = 0,
                                    requesttype = REQUEST_NEW,
                                    format = 1)

        swaprequest = PartitionSpec(fileSystemTypeGet("swap"),
                                    size = 128,
                                    grow = 0,
                                    requesttype = REQUEST_NEW,
                                    format = 1)

        id.autoClearPartType = CLEARPART_TYPE_LINUX
        id.autoClearPartDrives = []
        id.autoPartitionRequests = [rootrequest, bootrequest, swaprequest]


    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

	if expert:
	    self.skipLilo = 1
	else:
	    self.skipLilo = 0
