#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include "../isys/isys.h"

#include "log.h"
#include "modules.h"

void startPcmcia(moduleList modLoaded, moduleDeps modDeps, int flags) {
    pid_t child;
    char * probeArgs[] = { "/sbin/probe", NULL };
    char * cardmgrArgs[] = { "/sbin/cardmgr", "-o", "-m", "/modules", "-d", 
			NULL };
    int p[2];
    char buf[4096];
    int i;
    char * pcic;

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

    if (strstr(buf, "TCIC-2 probe: not found")) {
	logMessage("no pcic controller found");
	return;
    } else if (strstr(buf, "TCIC"))
	pcic = "tcic";
    else 
	pcic = "i82365";

    logMessage("need to load %s", pcic);

    if (mlLoadModule("pcmcia_core", modLoaded, modDeps, NULL, flags)) {
	logMessage("failed to load pcmcia_core");
	return;
    }
    if (mlLoadModule(pcic, modLoaded, modDeps, NULL, flags)) {
	logMessage("failed to load pcic");
	return;
    }
    if (mlLoadModule("ds", modLoaded, modDeps, NULL, flags)) {
	logMessage("failed to load ds");
	return;
    }

    if (!(child = fork())) {
	exit(cardmgr_main(5, cardmgrArgs));
    }

    logMessage("cardmgr running as pid %d", child);

    waitpid(child, NULL, 0);
}
