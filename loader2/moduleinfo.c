/*
 * moduleinfo.c - module info functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <alloca.h>
#include <ctype.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <stdio.h>

#ifndef NOTLOADER
#include "log.h"
#endif
#include "moduleinfo.h"

struct moduleInfo * getModuleList(moduleInfoSet mis, 
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

struct moduleInfo * findModuleInfo(moduleInfoSet mis, 
                                   const char * moduleName) {
    int i;
    struct moduleInfo * found = NULL;

    for (i = 0; i < mis->numModules; i++) {
        if (!strcmp(moduleName, mis->moduleList[i].moduleName)) {
            if (!found)
                found = mis->moduleList + i;
            else if (found->locationID && !mis->moduleList[i].locationID)
                ;
            else
                found = mis->moduleList + i;
        }
    }

    return found;
}

moduleInfoSet newModuleInfoSet(void) {
    return calloc(sizeof(struct moduleInfoSet_s), 1);
}

/* filename: file to read module-info from
 * mis: moduleInfoSet
 * location: moduleBallLocation struct describing the location of 
 *           these modules.  (may be NULL)
 * override: 1 if modules from this module ball should override old ones
 *           of the same name.
 */
int readModuleInfo(const char * filename, moduleInfoSet mis, 
                   void * location, int override) {
    int fd, isIndented;
    char * buf, * start, * next = NULL, * chptr;
    struct stat sb;
    char oldch;
    struct moduleInfo * nextModule;
    int modulesAlloced;
    int i;
    int found = 0, skipModule = 0;

    fd = open(filename, O_RDONLY);
    if (fd < 0) return -1;
 
    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    i = read(fd, buf, sb.st_size);
    buf[sb.st_size] = '\0';
    close(fd);

    if (i != sb.st_size)
        return -1;

    nextModule = NULL;
    modulesAlloced = mis->numModules;

    if (strncmp(buf, "Version 0\n", 10)) return -1;

    start = buf + 10;
    while (start && *start) {
        chptr = strchr(start, '\n');
        if (chptr) {
            /* slice and dice */
            next = chptr + 1;
        } else {
            chptr += strlen(start) - 1;
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
                if (nextModule && nextModule->moduleName &&
                    nextModule == (mis->moduleList + mis->numModules)) {
                        mis->numModules++; 
                }

                if (mis->numModules == modulesAlloced) {
                    modulesAlloced += 5;
                    mis->moduleList = realloc(mis->moduleList,
                        modulesAlloced * sizeof(*mis->moduleList));
                }

                nextModule = NULL;
                found = 0;
                skipModule = 0;
                for (i = 0; i < mis->numModules; i++) {
                    if (!strcmp(mis->moduleList[i].moduleName, start)) {
                        if (override) 
                            nextModule = mis->moduleList + i;
                        else
                            skipModule = 1;
                        found = 1;
                        break;
                    }
                }

                if (!found && !nextModule) {
                    nextModule = mis->moduleList + mis->numModules;

                    nextModule->moduleName = strdup(start);
                } 

                if (nextModule) {
                    nextModule->major = DRIVER_NONE;
                    nextModule->minor = DRIVER_MINOR_NONE;
                    nextModule->description = NULL;
                    nextModule->flags = 0;
                    nextModule->args = NULL;
                    nextModule->numArgs = 0;
                    nextModule->locationID = location;
                }
            } else if (!nextModule && skipModule) {
                /* we're skipping this one (not overriding), do nothing */
            } else if (!nextModule && skipModule) {
                /* ACK! syntax error */
                fprintf(stderr, "module-info syntax error in %s\n", filename);
                return 1;
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
                } else if (!strcmp(chptr, "scsi_hostadapter") ||
                           !strcmp(chptr, "scsi")) {
                    nextModule->major = DRIVER_SCSI;
                } else if (!strcmp(chptr, "pcmcia")) {
                    nextModule->major = DRIVER_PCMCIA;
                } else if (!strcmp(chptr, "fs")) {
                    nextModule->major = DRIVER_FS;
                } else if (!strcmp(chptr, "cdrom")) {
                    nextModule->major = DRIVER_CDROM;
                } else if (!strcmp(chptr, "ide")) {
                    nextModule->major = DRIVER_IDE;
                } else {
                    nextModule->major = DRIVER_OTHER;
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

    /* do we need to add in this last module? */
    if (nextModule && ((nextModule - mis->moduleList) == mis->numModules))
        mis->numModules++;

    return 0;
}

void freeModuleInfoSet(moduleInfoSet mis) {
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
