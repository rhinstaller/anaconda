#include <popt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../isys/isys.h"

int main(int argc, char ** argv) {
    poptContext optCon;
    char * modInfoFile = "/boot/module-info";
    enum driverMajor major;
    char * type;
    struct moduleInfo * list, * m;
    int rc;
    struct poptOption optionTable[] = {
	    { "modinfo", 'm', POPT_ARG_STRING, &modInfoFile, 0 },
	    POPT_AUTOHELP
	    { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext(NULL, argc, argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    if (isysReadModuleInfo(modInfoFile)) {
        fprintf(stderr, "Failed to read %s\n", modInfoFile);
	exit(1);
    }

    while ((type = poptGetArg(optCon))) {
        if (!strcasecmp(type, "scsi")) {
	    major = DRIVER_SCSI;
	} else if (!strcasecmp(type, "net")) {
	    major = DRIVER_NET;
	} else if (!strcasecmp(type, "fs")) {
	    major = DRIVER_FS;
	} else {
	    fprintf(stderr, "type must be one of scsi, net, fs\n");
	    exit(1);
	}

	list = isysGetModuleList(major);
	for (m = list; m && m->moduleName; m++)
	    printf("%s\n", m->moduleName);
	free(list);
    }

    return 0;
}
