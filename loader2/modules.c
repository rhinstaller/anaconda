/*
 * modules.c - module loading functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1999 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

#include "loader.h"
#include "log.h"
#include "modules.h"
#include "modstubs.h"
#include "windows.h"

#include "../isys/cpio.h"

static int writeModulesConf(moduleList list, int fd);
static struct extractedModule * extractModules (char * const * modNames,
                                                struct extractedModule * oldPaths,
                                                struct moduleBallLocation * location);

/* pass in the type of device (eth or tr) that you're looking for */
static int ethCount(const char * type) {
    int fd;
    char buf[16384];
    int i;
    char * chptr;
    int count = 0;

    fd = open("/proc/net/dev", O_RDONLY);
    i = read(fd, buf, sizeof(buf) - 1);
    buf[i] = '\0';

    /* skip first two header lines */
    chptr = strchr(buf, '\n') + 1;
    chptr = strchr(chptr, '\n') + 1;

    while (chptr) {
        while (*chptr && isspace(*chptr)) chptr++;
        if (!strncmp(chptr, type, strlen(type)))
            count++;
        chptr = strchr(chptr, '\n');
        if (chptr) chptr++;
    }

    return count;
}

static int scsiCount(void) {
    FILE *f;
    char buf[16384];
    int count = 0;
    
    f = fopen("/tmp/modules.conf", "r");
    if (!f)
        return 0;
    while (fgets(buf, sizeof(buf) - 1, f)) {
        if (!strncmp(buf, "alias scsi_hostadapter", 22))
            count++;
    }
    fclose(f);
    return count;
}


static int scsiDiskCount(void) {
    struct device ** devices;
    int i = 0;

    devices = probeDevices(CLASS_HD, BUS_SCSI, PROBE_ALL);
    if (!devices)
        return 0;

    for (i = 0; devices[i]; i++);

    return i;
}

int mlReadLoadedList(moduleList * mlp) {
    int fd;
    char * start;
    char * end;
    char buf[4096];
    struct stat sb;
    int i;
    moduleList ml;

    if ((fd = open("/proc/modules", O_RDONLY)) < 0)
        return -1;

    fstat(fd, &sb);
    i = read(fd, buf, sizeof(buf));
    buf[i] = '\0';
    close(fd);

    ml = malloc(sizeof(*ml));
    ml->numModules = 0;

    start = buf;
    while (start && *start) {
        end = start;
        while (!isspace(*end) && *end != '\n') end++;
        *end = '\0';
        ml->mods[ml->numModules].name = strdup(start);
        ml->mods[ml->numModules].args = NULL;
        ml->mods[ml->numModules].path = NULL;
        ml->mods[ml->numModules].weLoaded = 0;
        *end = ' ';
        ml->numModules++;
        start = strchr(end, '\n');
        if (start) start++;
    }

    *mlp = ml;

    return 0;
}

/* this leaks memory if their is a loop in the modules. oh well. */
char ** tsortModules(moduleList modLoaded, moduleDeps ml, char ** args, 
                     int depth, char *** listPtr, int * listSizePtr) {
    int listSize;
    char ** list;
    char ** next;
    char ** deps;
    
    if (!depth) {
        int count;

        listSize = 5;
        list = malloc((listSize + 1) * sizeof(*list));
        *list = NULL;

        listPtr = &list;
        listSizePtr = &listSize;

        for (deps = args, count = 0; *deps; deps++, count++);
    } else {
        list = *listPtr;
        listSize = *listSizePtr;
    }

    if (depth++ > 100) {
        return NULL;
    }

    while (*args) {
        /* don't load it twice */
        next = list;
        while (*next && strcmp(*next, *args)) next++;

        if (*next || mlModuleInList(*args, modLoaded)) {
            args++;
            continue;
        }

        /* load everything this depends on */
        deps = mlGetDeps(ml, *args);
        if (deps) {
            if (!tsortModules(modLoaded, ml, deps, depth, 
                              listPtr, listSizePtr))
                return NULL;
            
            list = *listPtr;
            listSize = *listSizePtr;
        }           

        /* add this to the list */
        next = list;
        while (*next) next++;

        if ((next - list) >= listSize) {
            int count = next - list;

            listSize += 10;
            /* leave room for a NULL */
            list = realloc(list, sizeof(*list) * (listSize + 1));

            *listSizePtr = listSize;
            *listPtr = list;

            next = list + count;
        }

        next[0] = *args;
        next[1] = NULL;

        args++;
    }

    return list;
}

int mlModuleInList(const char * modName, moduleList list) {
    int i;

    if (!list) return 0;

    for(i = 0; i < list->numModules; i++) 
        if (!strcmp(list->mods[i].name, modName)) return 1;

    return 0;
}

/* load a single module.  this is the real workhorse of loading modules */
static int loadModule(const char * modName, struct extractedModule * path,
                      moduleList modLoaded, char ** args, 
                      moduleInfoSet modInfo, int flags) {
    char fileName[300];
    char ** argPtr, ** newArgs, ** arg;
    struct moduleInfo * mi = NULL;
    int deviceCount = -1;
    int popWindow = 0;
    int rc, child, i, status;

    /* don't need to load a module that's already loaded */
    if (mlModuleInList(modName, modLoaded))
        return 0;

    if (modInfo && (mi = findModuleInfo(modInfo, modName))) {
        if ((mi->major == DRIVER_NET) && (mi->minor == DRIVER_MINOR_ETHERNET)) {
            deviceCount = ethCount("eth");
        } else if ((mi->major == DRIVER_NET) && (mi->minor == DRIVER_MINOR_TR)) {
            deviceCount = ethCount("tr");
        }

        if (mi->major == DRIVER_SCSI) {
            deviceCount = scsiCount();
            startNewt(flags);
            scsiWindow(modName);
            popWindow = 1;
        }
    }

    sprintf(fileName, "%s.o", modName);
    for (argPtr = args; argPtr && *argPtr; argPtr++) {
        strcat(fileName, " ");
        strcat(fileName, *argPtr);
    }

    if (FL_TESTING(flags)) {
        logMessage("would have insmod %s (%s)", path, fileName);
        rc = 0;
    } else {
        if (!(child = fork())) {
            int fd = open("/dev/tty3", O_RDWR);

            dup2(fd, 0);
            dup2(fd, 1);
            dup2(fd, 2);
            close(fd);
            
            rc = insmod(path->path, NULL, args);
            _exit(rc);
        }

        waitpid(child, &status, 0);
        
        if (!WIFEXITED(status) || WEXITSTATUS(status)) {
            rc = 1;
        } else {
            rc = 0;
        }
    }

    if (!rc) {
        int num = modLoaded->numModules;

        modLoaded->mods[num].name = strdup(modName);
        modLoaded->mods[num].weLoaded = 1;
        modLoaded->mods[num].path =
            path->location ? strdup(path->location) : NULL;
        modLoaded->mods[num].firstDevNum = -1;
        modLoaded->mods[num].lastDevNum = -1;
        modLoaded->mods[num].written = 0;
        
        if (mi) {
            modLoaded->mods[num].major = mi->major;
            modLoaded->mods[num].minor = mi->minor;
            
            if (deviceCount >= 0) {
                if ((mi->major == DRIVER_NET) && 
                    (mi->minor == DRIVER_MINOR_ETHERNET)) {
                    modLoaded->mods[num].firstDevNum = deviceCount;
                    modLoaded->mods[num].lastDevNum = ethCount("eth") - 1;
                } else if ((mi->major == DRIVER_NET) && 
                           (mi->minor == DRIVER_MINOR_TR)) {
                    modLoaded->mods[num].firstDevNum = deviceCount;
                    modLoaded->mods[num].lastDevNum = ethCount("tr") - 1;
                } else if (mi->major == DRIVER_SCSI) {
                    modLoaded->mods[num].firstDevNum = deviceCount;
                    modLoaded->mods[num].lastDevNum = scsiDiskCount() - 1;
                }
            }
	} else {
	    modLoaded->mods[num].major = DRIVER_NONE;
	    modLoaded->mods[num].minor = DRIVER_MINOR_NONE;
	}
        if (args) {
            for (i=0, arg = args; *arg; arg++, i++);
            newArgs = malloc(sizeof(*newArgs) * (i + 1));
            for (i = 0, arg = args; *arg; arg++, i++)
                newArgs[i] = strdup(*arg);
            newArgs[i] = NULL;
        } else {
            newArgs = NULL;
        }
        
        modLoaded->mods[modLoaded->numModules++].args = newArgs;
    }
    
    if (popWindow) {
        sleep(1);
        newtPopWindow();
    }
    
    return rc;
}

/* handle loading a set of modules including their dependencies.  also has
 * a nasty evil hack for handling usb-storage removal/reloading for scsi
 * device ordering. */
/* JKFIXME: the location argument is a hack to handle modules 
 * without module-info that I know need to be loaded from other than
 * /modules/modules.cgz.  should module-info be extended to cover 
 * *ALL* modules?  this would probably want for auto module-info generation */
static int doLoadModules(const char * origModNames, moduleList modLoaded,
                         moduleDeps modDeps, moduleInfoSet modInfo,
                         int flags, const char * argModule, char ** args,
                         struct moduleBallLocation * modLocation) {
    char * modNames;
    char * start, * next, * end;
    char ** initialList;
    char ** list, ** l;
    char items[1024] = ""; /* 1024 characters should be enough... */
    struct extractedModule * paths, * p;
    struct moduleBallLocation *location = NULL;
    int i;
    int reloadUsbStorage;

    struct moduleInfo * mi;

    start = modNames = alloca(strlen(origModNames) + 1);
    strcpy(modNames, origModNames);

    next = start;
    i = 1;
    while (*next) {
        if (*next == ':') i++;
        next++;
    }

    initialList = alloca(sizeof(*initialList) * (i + 1));

    i = 0;
    while (start) {
        next = end = strchr(start, ':');
        if (next) {
            *end = '\0'; 
            next++;
        }

        if (mlModuleInList(start, modLoaded)) {
            /* already loaded, we don't need to load it again */
            start = next;
            continue;
        }

        initialList[i++] = start;
        start = next;
    }

    initialList[i] = NULL;

    list = tsortModules(modLoaded, modDeps, initialList, 0, NULL, NULL);
    if (!list) {
        logMessage("ERROR: loop in module dependencies; not inserting");
        return 1;
    }

    for (i = 0; list[i]; i++) {
        strcat(items, " ");
        strcat(items, list[i]);
    }

    logMessage("modules to insert%s", items);

    paths = NULL;
    reloadUsbStorage = 0;
    if (modInfo) {
        for (i = 0; list[i]; i++) {
            mi = findModuleInfo(modInfo, list[i]);

            if (mi && mi->locationID) {
                location = mi->locationID;
            }

            if (mi && mi->major == DRIVER_SCSI) {
                reloadUsbStorage = 1;
            }
        }
    }

    /* JKFIXME: this is a hack to handle an explicit location for modules */
    if (!location && modLocation)
	location = modLocation;

    paths = extractModules(list, paths, location);

    i = 0;
    if (!paths) {
        logMessage("no modules found -- aborting insertion");
        return i;
    }

    *items = '\0';
    for (l = list, p = paths; *l && p; l++, p++) {
        if (!p->path) {
            if (*items) strcat(items, " ");
            strcat(items, *l);
            i++;
        }
    }

    if (*items) logMessage("module(s) %s not found", items);

    if (reloadUsbStorage) {
        /* JKFIXME: here are the big hacks... for now, just described.
         * 1) figure out which scsi devs are claimed by usb-storage.
         *    if lastScsiDev == usb-storage->lastDev, 
         *    lastScsiDev = usb->firstDev.  else, log that we're screwed.
         * 2) if stage2 is cdrom and mounted, umount stage2, umount cdrom
         * 3) rmmod usb-storage
         */
    }

    /* insert the modules now */

    for(l = list, p = paths; paths && *l; l++, p++) {
        if (!p->path)
            /* no path for this module */
            continue;
        if (loadModule(*l, p, modLoaded,
                       (argModule && !strcmp(argModule, *l)) ? args : NULL,
                       modInfo, flags)) {
            logMessage("failed to insert %s", *p);
        } else {
            logMessage("inserted %s", p->path);
        }
    }

    if (reloadUsbStorage) {
        /* JKFIXME: here's the rest of the hacks.  basically do the reverse
         * of what we did before.
         */
    }

    if (!FL_TESTING(flags)) {
        int fd;

        fd = open("/tmp/modules.conf", O_WRONLY | O_CREAT | O_APPEND, 0666);
        if (fd == -1) {
            logMessage("error appending to /tmp/modules.conf: %s\n",
                       strerror(errno));
        } else {
            writeModulesConf(modLoaded, fd);
            close(fd);
        }
    }

    for (p = paths; p->path; p++) {
        unlink(p->path);
        free(p->path);
        if (p->location) free(p->location);
    }

    free(paths);
    free(list);

    logMessage("load module set done");

    return i;
}

/* load a module with a given list of arguments */
int mlLoadModule(const char * module, moduleList modLoaded, 
                 moduleDeps modDeps, moduleInfoSet modInfo, 
                 char ** args, int flags) {
    return doLoadModules(module, modLoaded, modDeps, modInfo, flags, module,
                         args, NULL);
}

/* loads a : separated list of modules */
int mlLoadModuleSet(const char * modNames, 
                    moduleList modLoaded, moduleDeps modDeps, 
                    moduleInfoSet modInfo, int flags) {
    return doLoadModules(modNames, modLoaded, modDeps, modInfo, 
                         flags, NULL, NULL, NULL);
}

/* like mlLoadModuleSet but from an explicit location */
/* JKFIXME: this is a hack */
int mlLoadModuleSetLocation(const char * modNames,
			    moduleList modLoaded, moduleDeps modDeps,
			    moduleInfoSet modInfo, int flags,
			    struct moduleBallLocation * location) {
    return doLoadModules(modNames, modLoaded, modDeps, modInfo, 
                         flags, NULL, NULL, location);
}

static int writeModulesConf(moduleList list, int fd) {
    int i;
    struct loadedModuleInfo * lm;
    int ethNum;
    int scsiNum = scsiCount();
    char buf[16384], buf2[512]; /* these will be enough for anyone... */
    char * tmp, ** arg;

    if (!list) return 0;

    for (i = 0, lm = list->mods; i < list->numModules; i++, lm++) {
        if (!lm->weLoaded) continue;
        if (lm->written) continue;
        lm->written = 1;

        /* JKFIXME: this is a hack for the fact that these are now
         * DRIVER_SCSI so we can get /tmp/scsidisks, but we don't
         * want them in modules.conf  :/ */
        if (!strcmp(lm->name, "usb-storage") ||
            !strcmp(lm->name, "sbp2")) {
            continue;
        }

        if (lm->major != DRIVER_NONE) {
            strcpy(buf, "alias ");
            switch (lm->major) {
            case DRIVER_SCSI:
                /* originally set to # of scsi_hostadapter already in 
                 * /tmp/modules.conf.  then we increment ourselves */
                if (scsiNum)
                    sprintf(buf2, "scsi_hostadapter%d ", scsiNum);
                else
                    strcpy(buf2, "scsi_hostadapter ");
                scsiNum++;
                strcat(buf, buf2);
                break;

            case DRIVER_NET:
                switch(lm->minor) {
                case DRIVER_MINOR_ETHERNET:
                    tmp = "eth";
                    break;
                case DRIVER_MINOR_TR:
                    tmp = "tr";
                    break;
                default:
                    logMessage("WARNING: got net driver that's not ethernet or tr");
                    tmp = "";
                }

                for (ethNum = lm->firstDevNum; 
                     ethNum <= lm->lastDevNum; ethNum++) {
                    sprintf(buf2, "%s%d ", tmp, ethNum);
                    if (ethNum != lm->lastDevNum) {
                        strcat(buf2, lm->name);
                        strcat(buf2, "\nalias ");
                    }
                    strcat(buf, buf2);
                }

                break;

            default:
                break;
            }

            strcat(buf, lm->name);
            strcat(buf, "\n");
            write(fd, buf, strlen(buf));
        }
            
        if (lm->args) {
            strcpy(buf, "options ");
            strcat(buf, lm->name);
            for (arg = lm->args; *arg; arg++) {
                strcat(buf, " ");
                strcat(buf, *arg);
            }
            strcat(buf, "\n");
            write(fd, buf, strlen(buf));
        }
    }

    /* JKFIXME: used to have special casing for iucv stuff on s390 */

    return 0;
}

/* writes out /tmp/scsidisks with a scsi disk / module correspondence.
 * format is sd%c  adapter
 */
void writeScsiDisks(moduleList list) {
    int i, fd, num;
    struct loadedModuleInfo * lm;
    char buf[512];

    if (!list) return;

    if ((fd = open("/tmp/scsidisks", O_WRONLY | O_CREAT, 0666)) == -1) {
        logMessage("error opening /tmp/scsidisks: %s", strerror(errno));
        return;
    }

    for (i = 0, lm = list->mods; i < list->numModules; i++, lm++) {
        if (!lm->weLoaded) continue;
        if (lm->major != DRIVER_SCSI) continue;

        for (num = lm->firstDevNum; num <= lm->lastDevNum; num++) {
            if (num < 26)
                sprintf(buf, "sd%c\t%s\n", 'a' + num, lm->name);
            else {
                unsigned int one, two;
                one = num / 26;
                two = num % 26;

                sprintf(buf, "sd%c%c\t%s\n", 'a' + one - 1, 
                        'a' + two, lm->name);
            }
            write(fd, buf, strlen(buf));
        }
    }
     
    close(fd);
    return;
}

/* JKFIXME: needs a way to know about module locations.  also, we should
 * extract them to a ramfs instead of /tmp */
static struct extractedModule * extractModules (char * const * modNames,
                                                struct extractedModule * oldPaths,
                                                struct moduleBallLocation * location) {

    gzFile fd;
    char * ballPath;
    struct cpioFileMapping * map;
    int i, numMaps, rc;
    char * const * m;
    char fn[255];
    const char * failedFile;
    struct stat sb;
    struct utsname u;

    uname(&u);

    /* JKFIXME: handle driver disk path somehow */
    if (!location)
        ballPath = strdup("/modules/modules.cgz");
    else
        ballPath = strdup(location->path);

    fd = gunzip_open(ballPath);
    if (!fd) {
        logMessage("failed to open %s", ballPath);
        free(ballPath);
        return NULL;
    }

    for(m = modNames, i = 0; *m; i++, m++);

    map = alloca(sizeof(*map) * i);
    memset(map, 0, sizeof(*map) * i);

    if (!oldPaths)
        /* +1 NULL to terminate the list */
        oldPaths = calloc(i + 1, sizeof(*oldPaths));

    for (m = modNames, i = 0, numMaps = 0; *m; m++, i++) {
        /* if we don't know the path of this module yet, "figure" it out */
        if (!oldPaths[i].path) {
            map[numMaps].archivePath = alloca(strlen(u.release) + 
                                              strlen(*m) + 25);
            sprintf(map[numMaps].archivePath, "%s/%s.o", u.release, *m);
            map[numMaps].fsPath = alloca(10 + strlen(*m));
            sprintf(map[numMaps].fsPath, "/tmp/%s.o", *m);
            unlink(map[numMaps].fsPath);
            map[numMaps].mapFlags = CPIO_MAP_PATH;
            numMaps++;
        }
    }

    if (!numMaps) {
        gunzip_close(fd);
        free(ballPath);
        return oldPaths;
    }

    qsort(map, numMaps, sizeof(*map), myCpioFileMapCmp);
    rc = myCpioInstallArchive(fd, map, numMaps, NULL, NULL, &failedFile);

    gunzip_close(fd);

    for (m = modNames, i = 0, numMaps = 0; *m; m++, i++) {
        if (!oldPaths[i].path) {
            sprintf(fn, "/tmp/%s.o", modNames[i]);
            if (!stat(fn, &sb)) {
                oldPaths[i].path = strdup(fn);
                /* JKFIXME: this is copied from the old stuff -- do we really need it? */
                if (location && location->path) {
                    oldPaths[i].location = strdup(location->path);
                    if (location->title) 
                        logMessage("module %s found on driver disk %s", 
                                   modNames[i], location->title);
                    logMessage("loaded %s from %s", modNames[i], 
			       location->path);
                } else
                    logMessage("loaded %s from /modules/modules.cgz", modNames[i]);
            }
            numMaps++;
        }
    }

    free(ballPath);
    return oldPaths;
}
