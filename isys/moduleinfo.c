#include <alloca.h>
#include <ctype.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "isys.h"

struct moduleInfoSet_s {
    struct moduleInfo * moduleList;
    int numModules;
};

struct moduleInfo * isysGetModuleList(moduleInfoSet mis, 
				      enum driverMajor major) {
    struct moduleInfo * miList, * next;
    int i;

    next = miList = malloc(sizeof(*miList) * mis->numModules + 1);
    for (i = 0; i < mis->numModules; i++) {
	if (mis->moduleList[i].major == major || major == DRIVER_NONE) {
	    *next = mis->moduleList[i];
	    next++;
	}
    }

    if (next == miList) {
	free(next);
	return NULL;
    }

    next->moduleName = NULL;
    next++;

    miList = realloc(miList, sizeof(*miList) * (next - miList));
    return miList;
}

struct moduleInfo * isysFindModuleInfo(moduleInfoSet mis, 
				       const char * moduleName) {
    int i;

    for (i = 0; i < mis->numModules; i++)
	if (!strcmp(moduleName, mis->moduleList[i].moduleName))
	    return mis->moduleList + i;

    return NULL;
}

moduleInfoSet isysNewModuleInfoSet(void) {
    return calloc(sizeof(struct moduleInfoSet_s), 1);
}

int isysReadModuleInfo(const char * filename, moduleInfoSet mis) {
    int fd, isIndented;
    char * buf, * start, * next, * chptr;
    struct stat sb;
    char oldch;
    struct moduleInfo * nextModule;
    int modulesAlloced;

    fd = open(filename, O_RDONLY);
    if (fd < 0) return -1;
 
    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    read(fd, buf, sb.st_size);
    buf[sb.st_size] = '\0';
    close(fd);

    nextModule = mis->moduleList;
    modulesAlloced = mis->numModules;

    if (strncmp(buf, "Version 0\n", 10)) return -1;

    start = buf + 10;
    while (start && *start) {
	chptr = strchr(start, '\n');
	if (chptr) {
	    /* slice and dice */
	    next = chptr + 1;
	} else {
	    chptr + strlen(start) - 1;
	}

	chptr--;
	while (isspace(*chptr)) chptr--;
	chptr++;
	*chptr = '\0';

	isIndented = 0;
	if (isspace(*start)) {
	    while (isspace(*start) && *start != '\n') start++;
	    isIndented = 1;
	}

	if (*start != '\n' && *start && *start != '#') {
	    if (!isIndented) {
		if (nextModule && nextModule->moduleName) mis->numModules++;

		if (mis->numModules == modulesAlloced) {
		    modulesAlloced += 5;
		    mis->moduleList = realloc(mis->moduleList,
			modulesAlloced * sizeof(*mis->moduleList));
		}
		nextModule = mis->moduleList + mis->numModules;
		nextModule->moduleName = strdup(start);
		nextModule->major = DRIVER_NONE;
		nextModule->minor = DRIVER_MINOR_NONE;
		nextModule->description = NULL;
		nextModule->args = NULL;
		nextModule->numArgs = 0;
	    } else if (nextModule->major == DRIVER_NONE) {
		chptr = start + strlen(start) - 1;
		while (!isspace(*chptr) && chptr > start) chptr--;
		if (chptr != start) chptr++;

		if (!strcmp(chptr, "eth")) {
		    nextModule->major = DRIVER_NET;
		    nextModule->minor = DRIVER_MINOR_ETHERNET;
		} else if (!strcmp(chptr, "tr")) {
		    nextModule->major = DRIVER_NET;
		    nextModule->minor = DRIVER_MINOR_TR;
		} else if (!strcmp(chptr, "plip")) {
		    nextModule->major = DRIVER_NET;
		    nextModule->minor = DRIVER_MINOR_PLIP;
		} else if (!strcmp(chptr, "scsi_hostadapter")) {
		    nextModule->major = DRIVER_SCSI;
		} else if (!strcmp(chptr, "cdrom")) {
		    nextModule->major = DRIVER_CDROM;
		}
	    } else if (!nextModule->description) {
		chptr = start + strlen(start) - 1;
		if (*start == '"' && *chptr == '"') {
		    start++;
		    *chptr = '\0';
		    nextModule->description = strdup(start);
		}
	    } else {
		nextModule->args = realloc(nextModule->args,
			sizeof(*nextModule->args) * (nextModule->numArgs + 1));
		chptr = start;
		while (!isspace(*chptr) && *chptr) chptr++;
		if (*chptr) {
		    oldch = *chptr;
		    *chptr = '\0';
		    nextModule->args[nextModule->numArgs].arg = strdup(start);

		    start = chptr + 1;
		    while (*start && isspace(*start)) start++;

		    if (*start == '"') {
			start++;
			chptr = strchr(start, '"');
			if (chptr) {
			    *chptr = '\0';
			    nextModule->args[nextModule->numArgs].description = 
				strdup(start);
			    nextModule->numArgs++;
			}
		    }
		}
	    }
	}

	start = next;
    }

    if (nextModule && nextModule->moduleName) mis->numModules++;
    mis->numModules = nextModule - mis->moduleList;

    return 0;
}

void isysFreeModuleInfoSet(moduleInfoSet mis) {
    int i, j;

    for (i = 0; i < mis->numModules; i++) {
        if (mis->moduleList[i].moduleName) 
	    free(mis->moduleList[i].moduleName);

        if (mis->moduleList[i].description) 
	    free(mis->moduleList[i].description);

	for (j = 0; i < mis->moduleList[i].numArgs; j++) {
	    if (mis->moduleList[i].args[j].arg) 
		free(mis->moduleList[i].args[j].arg) ;
	    if (mis->moduleList[i].args[j].description) 
		free(mis->moduleList[i].args[j].description) ;
	}
    }

    free(mis);
}
