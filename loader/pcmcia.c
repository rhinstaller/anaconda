#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include "../isys/imount.h"
#include "../isys/isys.h"

#include "lang.h"
#include "loader.h"
#include "log.h"
#include "modules.h"
#include "windows.h"

int probe_main (int argc, char ** argv);
int cardmgr_main (int argc, char ** argv);

int startPcmcia(char * floppyDevice, moduleList modLoaded, moduleDeps modDeps,
		 moduleInfoSet modInfo, int flags) {
    pid_t child;
    char * probeArgs[] = { "/sbin/probe", NULL };
    char * cardmgrArgs[] = { "/sbin/cardmgr", "-o", "-m", "/modules", "-d", 
			NULL };
    int p[2];
    char buf[4096];
    int i, status;
    char * pcic = NULL;
    char * line = NULL;
    int rc;
    char * title = _("PC Card"); 
    char * text = _("Initializing PC Card Devices...");

    logMessage("in startPcmcia()");

    pipe(p);

    if (!(child = fork())) {
	close(p[0]);
	dup2(p[1], 1);
	close(p[1]);
	exit(probe_main(1, probeArgs));
    }

    close(p[1]);
    
    waitpid(child, NULL, 0);

    i = read(p[0], buf, sizeof(buf));
    close(p[0]);
    buf[i] = '\0';

    logMessage("pcmcia probe returned: |%s|", buf);
 
    /* So this is totally counter-intuitive. Just remember that probe
       stops printing output once it finds a pcic, so this is actually
       correct */

    line = strtok(buf, "\r\n");

    do {
	if (!strstr(line, "not found"))
	{
	    if (strstr(line, "TCIC"))
	        pcic = "tcic";
	    else
		pcic = "i82365";
	}
    } while((line = strtok(NULL, "\r\n")));

    if (!pcic)
    {
	logMessage("no pcic controller found");
	return 0;
    }

    logMessage("need to load %s", pcic);

    winStatus(40, 3, title, text);
    if (mlLoadModule("pcmcia_core", NULL, modLoaded, modDeps, 
		     NULL, modInfo, flags)) {
	logMessage("failed to load pcmcia_core -- ask for pcmciadd");
	rc = 1;
	newtPopWindow();
    } else {
	rc = 0;
    }

    while (rc) {
	rc = newtWinChoice(_("PCMCIA"), _("OK"), _("Cancel"),
		      _("Please insert your PCMCIA driver disk "
			"into your floppy drive now."));
	if (rc == 2) return LOADER_BACK;

	devMakeInode(floppyDevice, "/tmp/floppy");

	rc = 1;
	if (doPwMount("/tmp/floppy", "/modules", "ext2", 1, 0, NULL, 
		      NULL)) {
	    newtWinMessage(_("Error"), _("OK"), _("Failed to mount disk."));
	} else {
	    int fd;

	    fd = open("/modules/rhdd-6.1", O_RDONLY);
	    if (fd >= 0) {
		char buf[20];
		int i;

		i = read(fd, buf, 20);
		buf[9] = '\0';
		logMessage("read %s", buf);
		if (i == 9 && !strcmp(buf, "rhpcmcia\n")) {
		    winStatus(40, 3, title, text);
		    if (mlLoadModule("pcmcia_core", NULL, modLoaded, modDeps, 
				     NULL, modInfo, flags)) {
			newtPopWindow();
			newtWinMessage(_("Error"), _("OK"),
				_("That floppy does not look like a "
				  "Red Hat PCMCIA driver disk."));
		    }

		    rc = 0;
		}

		close(fd);
	    }

	    if (rc)
		umount("/modules");
	}
    }

    if (mlLoadModule(pcic, NULL, modLoaded, modDeps, NULL, 
		     modInfo, flags)) {
	logMessage("failed to load pcic");
	umount("/modules");
	return LOADER_ERROR;
    }

    if (mlLoadModule("ds", NULL, modLoaded, modDeps, NULL, 
		     modInfo, flags)) {
	logMessage("failed to load ds");
	umount("/modules");
	return LOADER_ERROR;
    }

    if (!(child = fork())) {
	exit(cardmgr_main(5, cardmgrArgs));
    }

    logMessage("cardmgr running as pid %d", child);

    waitpid(child, &status, 0);

    logMessage("cardmgr returned 0x%x", status);

    newtPopWindow();
    umount("/modules");
    
    return 0;
}
