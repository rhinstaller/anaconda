#include <stdlib.h>
#include <unistd.h>

#include <newt.h>

#include "cdrom.h"
#include "devices.h"
#include "lang.h"
#include "loader.h"
#include "windows.h"

#define CD_SCSI 2
#define CD_OTHER 3

static struct { char * modname, * devname; } transTable[] = {
	{ "cm206", "cm206cd" },
	{ "sonycd535", "cdu535" },
	{ NULL, NULL }
} ;

static int setupCDdevicePanel(int * type) {
    char * menuItems[3];
    int cdromType = 0, rc;

    menuItems[0] = "SCSI";
    menuItems[1] = _("Other CDROM");
    menuItems[2] = NULL;

    if (*type == CD_OTHER)
	cdromType = 1;

    rc = newtWinMenu(_("CDROM type"), _("What type of CDROM do you have?"),
		     30, 5, 5, 7, menuItems,
		     &cdromType, _("OK"), _("Back"), NULL);

    if (rc == 2) return LOADER_BACK;

    if (cdromType == 0)
	*type = CD_SCSI;
    else
	*type = CD_OTHER;

    return 0;
}

int setupCDdevice(struct knownDevices * kd, moduleInfoSet modInfo, 
		  moduleList modLoaded, moduleDeps * modDepsPtr, int flags) {
    int type = 0, rc = 0;
    int i;
    int done = 0;
    char * devName;

    while (!done) {
	rc = setupCDdevicePanel(&type);
	if (rc) return rc;

	switch (type) {
	  case CD_SCSI:
	    rc = devDeviceMenu(DRIVER_SCSI, modInfo, modLoaded, modDepsPtr, 
	    		       flags, NULL);
	    if (!rc) {
		kdFindScsiList(kd);
		/* we'll get called again if the scsi bus doesn't have a CDROM
		   drive on it */
		done = 1;
	    }
	    break;

	  case CD_OTHER:
	    rc = devDeviceMenu(DRIVER_CDROM, modInfo, modLoaded, modDepsPtr, 
	    		       flags, &devName);
	    if (!rc) {
		for (i = 0; transTable[i].modname; i++) {
		    if (!strcmp(devName, transTable[i].devname)) {
			devName = transTable[i].devname;
			break;
		    }
		}

		kdAddDevice(kd, CLASS_CDROM, devName, NULL);

		done = 1;
	    }
	    break;
	}
    } 

    winStatus(35, 3, "CDROM", _("Initializing CDROM..."));
    sleep(2);			/* some drivers need time to initialize */
    newtPopWindow();

    return 0;
}

