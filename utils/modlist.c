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
    char * mod;
    struct moduleInfo * list, * m;
    int rc, i;
    int showModInfo = 0;
    int ignoreMissing = 0;
    moduleInfoSet mis;
    struct moduleInfo * mi;
    struct poptOption optionTable[] = {
    	    { "ignore-missing", 'I', POPT_ARG_NONE, &ignoreMissing, 0,
	    	"Ignore modules not in modinfo file for --modinfo" },
	    { "modinfo", 'm', POPT_ARG_NONE, &showModInfo, 0,
	    	"Give output in module-info file for listed args" },
	    { "modinfo-file", 'f', POPT_ARG_STRING, &modInfoFile, 0,
	    	"Module info file to use"},
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

    mis = isysNewModuleInfoSet();
    if (isysReadModuleInfo(modInfoFile, mis, NULL)) {
        fprintf(stderr, "Failed to read %s\n", modInfoFile);
	exit(1);
    }

    if (showModInfo) {
        printf("Version 0\n");
	while ((mod = poptGetArg(optCon))) {
	    mi = isysFindModuleInfo(mis, mod);
	    if (mi) {
	    	printf("%s\n", mi->moduleName);
		switch (mi->major) {
		  case DRIVER_CDROM: printf("\tcdrom\n"); break;
		  case DRIVER_SCSI: printf("\tscsi\n"); break;
		  case DRIVER_FS: printf("\tfs\n"); break;
		  case DRIVER_NET: 
		    switch (mi->minor) {
		      case DRIVER_MINOR_ETHERNET: printf("\teth\n"); break;
		      case DRIVER_MINOR_TR: printf("\ttr\n"); break;
		      case DRIVER_MINOR_PLIP: printf("\tplip\n"); break;

		      default:
		      	fprintf(stderr, "unknown net minor type for %s\n",
				mi->moduleName);
			exit(1);
		    }
		    break;

		  default:
		    fprintf(stderr, "unknown device type for %s\n",
			    mi->moduleName);
		    exit(1);

		}
	    	printf("\t\"%s\"\n", mi->description);
	    	for (i = 0; i < mi->numArgs; i++) {
		    printf("\t%s \"%s\"\n", mi->args[i].arg,
		    	   mi->args[i].description);
		}
	    } else if (!ignoreMissing) {
	    	fprintf(stderr, "I know nothing about %s\n", mod);
		exit(1);
	    }
	}
    } else {
	while ((type = poptGetArg(optCon))) {
	    if (!strcasecmp(type, "scsi")) {
		major = DRIVER_SCSI;
	    } else if (!strcasecmp(type, "net")) {
		major = DRIVER_NET;
	    } else if (!strcasecmp(type, "fs")) {
		major = DRIVER_FS;
	    } else if (!strcasecmp(type, "cdrom")) {
		major = DRIVER_CDROM;
	    } else {
		fprintf(stderr, "type must be one of scsi, net, fs, cdrom\n");
		exit(1);
	    }

	    list = isysGetModuleList(mis, major);
	    for (m = list; m && m->moduleName; m++)
		printf("%s\n", m->moduleName);
	    free(list);
	}
    }

    return 0;
}
