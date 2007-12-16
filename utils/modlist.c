/*
 * modlist.c
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <popt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../isys/isys.h"
#include "moduleinfo.h"

int main(int argc, char ** argv) {
    poptContext optCon;
    char * modInfoFile = "/boot/module-info";
    enum driverMajor major;
    const char * type;
    const char * mod;
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

    optCon = poptGetContext(NULL, argc, (const char **) argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    mis = newModuleInfoSet();
    if (readModuleInfo(modInfoFile, mis, NULL, 0)) {
        fprintf(stderr, "Failed to read %s\n", modInfoFile);
	exit(1);
    }

    if (showModInfo) {
        printf("Version 0\n");
	while ((mod = poptGetArg(optCon))) {
	    mi = findModuleInfo(mis, mod);
	    if (mi) {
	    	printf("%s\n", mi->moduleName);
		switch (mi->major) {
		  case DRIVER_CDROM: printf("\tcdrom\n"); break;
		  case DRIVER_SCSI: printf("\tscsi\n"); break;
		  case DRIVER_FS: printf("\tfs\n"); break;
                  case DRIVER_PCMCIA: printf("\tpcmcia\n"); break;
                  case DRIVER_IDE: printf("\tide\n"); break;
                  case DRIVER_OTHER: printf("\tother\n"); break;
		  case DRIVER_NET: 
		    switch (mi->minor) {
		      case DRIVER_MINOR_ETHERNET: printf("\teth\n"); break;
		      case DRIVER_MINOR_TR: printf("\ttr\n"); break;

		      default:
		      	fprintf(stderr, "unknown net minor type for %s\n",
				mi->moduleName);
			exit(1);
		    }
		    break;

		  default:
		    fprintf(stderr, "unknown device type for %s (%d)\n",
			    mi->moduleName, mi->major);
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

	    list = getModuleList(mis, major);
	    for (m = list; m && m->moduleName; m++)
		printf("%s\n", m->moduleName);
	    free(list);
	}
    }

    return 0;
}
