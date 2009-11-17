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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <glib.h>

#include "../isys/isys.h"
#include "moduleinfo.h"

int main(int argc, char ** argv) {
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    gchar *modInfoFile = "/boot/module-info";
    gboolean ignoreMissing = FALSE, showModInfo = FALSE;
    gchar **remaining = NULL;
    enum driverMajor major;
    const char * type;
    const char * mod;
    struct moduleInfo * list, * m;
    int i, arg = 0;
    moduleInfoSet mis;
    struct moduleInfo * mi;
    GOptionEntry optionTable[] = {
        { "ignore-missing", 'I', 0, G_OPTION_ARG_NONE, &ignoreMissing,
          "Ignore modules not in modinfo file for --modinfo", NULL },
        { "modinfo", 'm', 0, G_OPTION_ARG_NONE, &showModInfo,
          "Give output in module-info file for listed args", NULL },
        { "modinfo-file", 'f', 0, G_OPTION_ARG_STRING, &modInfoFile,
          "Module info file to use", NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
    };

    g_option_context_add_main_entries(optCon, optionTable, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
       fprintf(stderr, "bad option: %s\n", optErr->message);
       g_error_free(optErr);
       g_option_context_free(optCon);
       g_strfreev(remaining);
       exit(1);
    }

    g_option_context_free(optCon);

    if (remaining == NULL) {
        exit(1);
    }

    mis = newModuleInfoSet();
    if (readModuleInfo(modInfoFile, mis, NULL, 0)) {
        fprintf(stderr, "Failed to read %s\n", modInfoFile);
	exit(1);
    }

    if (showModInfo) {
        printf("Version 0\n");
	while ((mod = remaining[arg]) != NULL) {
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
			g_strfreev(remaining);
			exit(1);
		    }
		    break;

		  default:
		    fprintf(stderr, "unknown device type for %s (%d)\n",
			    mi->moduleName, mi->major);
		    g_strfreev(remaining);
		    exit(1);

		}
	    	printf("\t\"%s\"\n", mi->description);
	    	for (i = 0; i < mi->numArgs; i++) {
		    printf("\t%s \"%s\"\n", mi->args[i].arg,
		    	   mi->args[i].description);
		}
	    } else if (!ignoreMissing) {
	    	fprintf(stderr, "I know nothing about %s\n", mod);
		g_strfreev(remaining);
		exit(1);
	    }
	    arg++;
	}
    } else {
	while ((type = remaining[arg]) != NULL) {
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
		g_strfreev(remaining);
		exit(1);
	    }

	    list = getModuleList(mis, major);
	    for (m = list; m && m->moduleName; m++)
		printf("%s\n", m->moduleName);
	    free(list);
	    arg++;
	}
    }

    g_strfreev(remaining);
    return 0;
}
