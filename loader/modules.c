#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#include <zlib.h>

#include "isys/imount.h"
#include "isys/isys.h"
#include "isys/cpio.h"

#include "lang.h"
#include "loader.h"
#include "log.h"
#include "modules.h"

struct moduleDependency_s {
    char * name;
    char ** deps;
};

static int ethCount(void) {
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
	if (!strncmp(chptr, "eth", 3))
	    count++;
	chptr = strchr(chptr, '\n');
	if (chptr) chptr++;
    }

    return count;
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
	ml->mods[ml->numModules].weLoaded = 0;
	*end = ' ';
	ml->numModules++;
	start = strchr(end, '\n');
	if (start) start++;
    }

    *mlp = ml;

    return 0;
}

void mlFreeList(moduleList ml) {
    int i;
    int j;

    for (i = 0; i < ml->numModules; i++) {
        free(ml->mods[i].name);
	if (ml->mods[i].args) {
	    for (j = 0; ml->mods[j].args[j]; j++)
		free(ml->mods[i].args[j]);
	    free(ml->mods[i].args);
	}
    }
    free(ml);
}

moduleDeps mlNewDeps(void) {
    moduleDeps md;

    md = malloc(sizeof(*md));
    md->name = NULL;
    md->deps = NULL;

    return md;
}

int mlLoadDeps(moduleDeps * moduleDepListPtr, const char * path) {
    int fd;
    char * buf;
    struct stat sb;
    char * start, * end, * chptr;
    int i, numItems;
    moduleDeps nextDep;
    moduleDeps moduleDepList = *moduleDepListPtr;

    fd = open(path, O_RDONLY);
    if (fd < 0) {
	return -1;
    }

    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    read(fd, buf, sb.st_size);
    buf[sb.st_size] = '\0';
    close(fd);

    start = buf;
    numItems = 0;
    while (start) {
	numItems++;
	start = strchr(start + 1, '\n');
    }

    for (nextDep = moduleDepList; nextDep->name; nextDep++) numItems++;

    moduleDepList = realloc(moduleDepList, sizeof(*moduleDepList) * numItems);
    for (nextDep = moduleDepList; nextDep->name; nextDep++) ;

    start = buf;
    while (start < (buf + sb.st_size) && *start) {
	end = strchr(start, '\n');
	*end = '\0';

	chptr = strchr(start, ':');
	if (!chptr) {
	    start = end + 1;
	    continue;
	}

	*chptr++ = '\0';
	while (*chptr && isspace(*chptr)) chptr++;
	if (!*chptr) {
	    start = end + 1;
	    continue;
	}

	/* found something */
	nextDep->name = strdup(start);
	nextDep->deps = malloc(sizeof(char *) * (strlen(chptr) + 1));
	start = chptr, i = 0;
	while (start && *start) {
	    chptr = strchr(start, ' ');
	    if (chptr) *chptr = '\0';
	    nextDep->deps[i++] = strdup(start);
	    if (chptr)
		start = chptr + 1;
	    else
		start = NULL;
	    while (start && *start && isspace(*start)) start++;
	}
	nextDep->deps[i] = NULL;
	nextDep->deps = realloc(nextDep->deps, sizeof(char *) * (i + 1));
	nextDep++;

	start = end + 1;
    }

    nextDep->name = NULL;
    nextDep->deps = NULL;
    moduleDepList = realloc(moduleDepList, sizeof(*moduleDepList) *
				(nextDep - moduleDepList + 1));

    *moduleDepListPtr = moduleDepList;

    return 0;
}

static void removeExtractedModule(char * path) {
    char * fn = alloca(strlen(path) + 20);

    sprintf(fn, "%s/modules.cgz", path);
    unlink(fn);
    rmdir(path);
}

static char * extractModule(char * location, char * modName) {
    char * pattern[] = { NULL, NULL };
    struct utsname un;
    gzFile from;
    gzFile to;
    int first = 1;
    int fd;
    char * buf;
    struct stat sb;
    int rc;
    int failed;
    char * toPath;

    uname(&un);

    pattern[0] = alloca(strlen(modName) + strlen(un.release) + 5);
    sprintf(pattern[0], "%s*/%s.o", un.release, modName);
    logMessage("extracting pattern %s", pattern[0]);

    devMakeInode("fd0", "/tmp/fd0");
    while (1) {
	failed = 0;

	if (doPwMount("/tmp/fd0", "/tmp/drivers", "vfat", 1, 0, NULL, NULL))
	    if (doPwMount("/tmp/fd0", "/tmp/drivers", "ext2", 1, 0, NULL, NULL))
		failed = 1;

	if (failed && !first) {
	    newtWinMessage(_("Error"), _("OK"), 
		    _("Failed to mount driver disk."));
	} else if (!failed) {
	    if ((fd = open("/tmp/drivers/rhdd-6.1", O_RDONLY)) < 0)
		failed = 1;
	    if (!failed) {
		fstat(fd, &sb);
		buf = malloc(sb.st_size + 1);
		read(fd, buf, sb.st_size);
		if (buf[sb.st_size - 1] == '\n')
		    sb.st_size--;
		buf[sb.st_size] = '\0';
		close(fd);

		failed = strcmp(buf, location);
		free(buf);
	    }

	    if (failed && !first) {
		umount("/tmp/drivers");
		newtWinMessage(_("Error"), _("OK"),
			_("The wrong diskette was inserted."));
	    }
	}

	if (!failed) {
	    from = gzopen("/tmp/drivers/modules.cgz", "r");
	    toPath = malloc(strlen(modName) + 30);
	    sprintf(toPath, "/tmp/modules/%s", modName);
	    mkdirChain(toPath);
	    strcat(toPath, "/modules.cgz");
	    to = gzopen(toPath, "w");

	    myCpioFilterArchive(from, to, pattern);

	    gzclose(from);
	    gzclose(to);
	    umount("/tmp/drivers");

	    sprintf(toPath, "/tmp/modules/%s", modName);
	    return toPath;
	}

	first = 0;

	ejectFloppy();
	rc = newtWinChoice(_("Driver Disk"), _("OK"), _("Cancel"),
		_("Please insert the %s driver disk now."), location);
	if (rc == 2) return NULL;
    }
}

int mlLoadModule(char * modName, char * location, moduleList modLoaded,
	         moduleDeps modDeps, char ** args, moduleInfoSet modInfo,
		 int flags) {
    moduleDeps dep;
    char ** nextDep, ** argPtr;
    char fileName[200];
    int rc, i;
    char ** arg, ** newArgs;
    struct moduleInfo * mi;
    int ethDevices = -1;
    pid_t child;
    int status;
    char * path = NULL;

    if (mlModuleInList(modName, modLoaded)) {
	return 0;
    }

    if (modInfo && (mi = isysFindModuleInfo(modInfo, modName))) {
	if (mi->major == DRIVER_NET && mi->minor == DRIVER_MINOR_ETHERNET) {
	    ethDevices = ethCount();
	}
    }

    for (dep = modDeps; dep->name && strcmp(dep->name, modName);
    	 dep++);

    if (dep && dep->deps) {
	nextDep = dep->deps;
	while (*nextDep) {
	    if (mlLoadModule(*nextDep, location, modLoaded, modDeps, NULL, modInfo, flags) && location)
		  mlLoadModule(*nextDep, NULL, modLoaded, modDeps, NULL, modInfo, flags);
	    nextDep++;
	}
    }

    if (location) {
	path = extractModule(location, modName); 
	if (!path) return 1;
    }

    sprintf(fileName, "%s.o", modName);
    for (argPtr = args; argPtr && *argPtr; argPtr++)  {
	strcat(fileName, " ");
	strcat(fileName, *argPtr);
    }

    sprintf(fileName, "%s.o", modName);

    if (FL_TESTING(flags)) {
	logMessage("would have insmod %s", fileName);
	rc = 0;
    } else {
	logMessage("going to insmod %s (path is %s)", fileName,
		   path ? path : "NULL");

	if (!(child = fork())) {
	    int fd = open("/dev/tty3", O_RDWR);

	    dup2(fd, 0);
	    dup2(fd, 1);
	    dup2(fd, 2);
	    close(fd);

	    rc = insmod(fileName, path, args);
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
	modLoaded->mods[modLoaded->numModules].name = strdup(modName);
	modLoaded->mods[modLoaded->numModules].weLoaded = 1;
	modLoaded->mods[modLoaded->numModules].path = path;
	modLoaded->mods[modLoaded->numModules].firstDevNum = -1;
	modLoaded->mods[modLoaded->numModules].lastDevNum = -1;

	if (ethDevices >= 0) {
	    modLoaded->mods[modLoaded->numModules].firstDevNum = ethDevices;
	    modLoaded->mods[modLoaded->numModules].lastDevNum = ethCount() - 1;
	}

	if (args) {
	    for (i = 0, arg = args; *arg; arg++, i++);
	    newArgs = malloc(sizeof(*newArgs) * (i + 1));
	    for (i = 0, arg = args; *arg; arg++, i++)
		newArgs[i] = strdup(*arg);
	    newArgs[i] = NULL;
	} else {
	    newArgs = NULL;
	}

	modLoaded->mods[modLoaded->numModules++].args = newArgs;
    } else {
	if (path) removeExtractedModule(path);
	free(path);
    }

    return rc;
}

char ** mlGetDeps(moduleDeps modDeps, const char * modName) {
    moduleDeps dep;
    
    for (dep = modDeps; dep->name && strcmp(dep->name, modName); dep++);

    if (dep) return dep->deps;

    return NULL;
}

int mlModuleInList(const char * modName, moduleList list) {
    int i;

    if (!list) return 0;

    for (i = 0; i < list->numModules; i++)
        if (!strcmp(list->mods[i].name, modName)) return 1;

    return 0;
}

int mlWriteConfModules(moduleList list, moduleInfoSet modInfo, int fd) {
    int i;
    struct loadedModuleInfo * lm;
    char buf[200], buf2[200];
    struct moduleInfo * mi;
    int scsiNum = 0;
    int ethNum;
    int trNum = 0;
    char ** arg;

    if (!list) return 0;

    for (i = 0, lm = list->mods; i < list->numModules; i++, lm++) {
    	if (!lm->weLoaded) continue;
	if ((mi = isysFindModuleInfo(modInfo, lm->name))) {
	    strcpy(buf, "alias ");
	    switch (mi->major) {
	      case DRIVER_CDROM:
		strcat(buf, "cdrom ");
		break;

	      case DRIVER_SCSI:
	      	if (scsiNum)
		    sprintf(buf2, "scsi_hostadapter%d ", scsiNum);
		else
		    strcpy(buf2, "scsi_hostadapter ");
		scsiNum++;
		strcat(buf, buf2);
		break;

	      case DRIVER_NET:
	        switch (mi->minor) {
		  case DRIVER_MINOR_ETHERNET:
		      for (ethNum = lm->firstDevNum; 
				ethNum <= lm->lastDevNum; ethNum++) {
			  sprintf(buf2, "eth%d ", ethNum);
			  if (ethNum != lm->lastDevNum) {
			      strcat(buf2, lm->name);
			      strcat(buf2, "\nalias ");
			  }
			  strcat(buf, buf2);
		      }
			  
		      break;
		  case DRIVER_MINOR_TR:
		      sprintf(buf2, "tr%d ", trNum++);
		      strcat(buf, buf2);
		      break;
		  default:
		}

	      default:
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

    return 0;
}
