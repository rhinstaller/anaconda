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

#include "lang.h"
#include "loader.h"
#include "log.h"
#include "misc.h"
#include "modules.h"
#include "devices.h"

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

static int scsiCount(void) {
    FILE *f;
    char buf[16384];
    int count = 0;

    f = fopen("/tmp/modules.conf", "r");
    if (!f)
	return 0;
    while (fgets(buf, sizeof(buf) - 1, f)) {
	if (!strncmp(buf, "scsi_hostadapter", 16))
	    count++;
    }
    fclose(f);
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
	    if (!tsortModules(modLoaded, ml, deps, depth, listPtr, listSizePtr))
		return NULL;

	    list = *listPtr;
	    listSize = *listSizePtr;

	    free(deps);
	}	    

	/* add this to the list */
	next = list;
	while (*next) next++;

	if ((next - list) >= listSize) {
	    listSize += 10;
	    /* leave room for a NULL */
	    list = realloc(list, sizeof(*list) * (listSize + 1));

	    *listSizePtr = listSize;
	    *listPtr = list;
	}

	next[0] = *args;
	next[1] = NULL;

	args++;
    }

    return list;
}

static int loadModule(const char * modName, char * path, moduleList modLoaded,
	         char ** args, moduleInfoSet modInfo, int flags) {
    char fileName[200];
    int rc, i;
    char ** arg, ** newArgs, ** argPtr;
    struct moduleInfo * mi = NULL;
    int ethDevices = -1;
    pid_t child;
    int status;

    if (mlModuleInList(modName, modLoaded))
	return 0;

    if (modInfo && (mi = isysFindModuleInfo(modInfo, modName))) {
	if (mi->major == DRIVER_NET && mi->minor == DRIVER_MINOR_ETHERNET) {
	    ethDevices = ethCount();
	}
    }

    sprintf(fileName, "%s.o", modName);
    for (argPtr = args; argPtr && *argPtr; argPtr++)  {
	strcat(fileName, " ");
	strcat(fileName, *argPtr);
    }

    if (FL_TESTING(flags)) {
	logMessage("would have insmod %s", path);
	rc = 0;
    } else {
	logMessage("going to insmod %s", path);

	if (!(child = fork())) {
	    int fd = open("/dev/tty3", O_RDWR);

	    dup2(fd, 0);
	    dup2(fd, 1);
	    dup2(fd, 2);
	    close(fd);

	    rc = insmod(path, NULL, args);
	    _exit(rc);
	}

	waitpid(child, &status, 0);

	if (!WIFEXITED(status) || WEXITSTATUS(status)) {
	    rc = 1;
	} else {
	    rc = 0;
	}

	logMessage("%s done w/ rc %d", path, rc);
    }

    if (!rc) {
	modLoaded->mods[modLoaded->numModules].name = strdup(modName);
	modLoaded->mods[modLoaded->numModules].weLoaded = 1;
	modLoaded->mods[modLoaded->numModules].path = strdup(path);
	modLoaded->mods[modLoaded->numModules].firstDevNum = -1;
	modLoaded->mods[modLoaded->numModules].lastDevNum = -1;
	modLoaded->mods[modLoaded->numModules].written = 0;
	
	if (ethDevices >= 0) {
	    modLoaded->mods[modLoaded->numModules].firstDevNum = ethDevices;
	    modLoaded->mods[modLoaded->numModules].lastDevNum = ethCount() - 1;
	}

	if (mi) {
	    modLoaded->mods[modLoaded->numModules].major = mi->major;
	    modLoaded->mods[modLoaded->numModules].minor = mi->minor;
	} else {
	    modLoaded->mods[modLoaded->numModules].major = DRIVER_NONE;
	    modLoaded->mods[modLoaded->numModules].minor = DRIVER_MINOR_NONE;
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
    }

    return rc;
}

/* loads a : separated list of modules. the arg only applies to the
   first module in the list */
int mlLoadModuleSet(const char * origModNames, 
		    moduleList modLoaded, moduleDeps modDeps, char ** args, 
		    moduleInfoSet modInfo, int flags) {
    char * modNames;
    char * end, * start, * next;
    char ** initialList;
    int i;
    char ** list, ** l;
    char ** paths, ** p;
    struct moduleInfo * mi;

    start = modNames = alloca(strlen(origModNames) + 1);
    strcpy(modNames, origModNames);

    next = start, i = 1;
    while (*next) {
	if (*next == ':') i++;
	next++;
    }

    initialList = alloca(sizeof(*initialList) * (i + 1));

    i = 0;
    while (start) {
	next = end = strchr(start, ':');
	if (next) *end = '\0', next++;

	if (mlModuleInList(start, modLoaded)) {
	    /* already loaded */
	    start = next;
	    continue;
	}

	initialList[i++] = start;

	start = next;
    }
    initialList[i] = NULL;

    list = tsortModules(modLoaded, modDeps, initialList, 0, NULL, NULL);
    if (!list) {
	logMessage("found loop in module dependencies; not inserting anything");
	return 1;
    }

    paths = NULL;
    if (modInfo) {
	for (i = 0; list[i]; i++) {
	    if (paths && paths[i]) continue;
	    mi = isysFindModuleInfo(modInfo, list[i]);

	    if (mi && mi->locationID)
		paths = extractModules(mi->locationID, list, paths); 
	    }
    }

    paths = extractModules(NULL, list, paths); 
    i = 0;
    if (!paths) {
	logMessage("no modules found -- aborting insertion\n");
	i++;
    } else {
	/* if any modules weren't found, holler */
	for (l = list, p = paths; *l && p; l++, p++) {
	    if (!*p) {
		logMessage("module %s not found -- aborting insertion",
			   *l);
		i++;
	    }
	}
    }

    /* insert the modules now */
    for (l = list, p = paths; !i && *l; l++, p++) {
	if (loadModule(*l, *p, modLoaded, 
		       !strcmp(initialList[0], *l) ? args : NULL, 
		       modInfo, flags)) {
	    logMessage("failed to insert %s -- bailing\n", *p);
	    i++;
	}
    }

    logMessage("done inserting modules");

    if (!FL_TESTING(flags)) {
	int fd;
	
	fd = open("/tmp/modules.conf", O_WRONLY | O_CREAT | O_APPEND,
		  0666);
	if (fd == -1) {
	    logMessage("error appending to /tmp/modules.conf: %s\n", 
		       strerror(errno));
	} else {
	    mlWriteConfModules(modLoaded, fd);
	    close(fd);
	}
    }

    logMessage("wrote modules.conf");
    
    for (p = paths; *p; p++) {
	unlink(*p);
	free(*p);
    }

    free(paths);
    free(list);

    logMessage("load module set done");

    return i;
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

int mlWriteConfModules(moduleList list, int fd) {
    int i;
    struct loadedModuleInfo * lm;
    char buf[200], buf2[200];
    int scsiNum;
    int ethNum;
    int trNum = 0;
    char ** arg;

    if (!list) return 0;

    scsiNum = scsiCount();
    
    for (i = 0, lm = list->mods; i < list->numModules; i++, lm++) {
    	if (!lm->weLoaded) continue;
	if (lm->written) continue;
	lm->written = 1;
	if (lm->major != DRIVER_NONE) {
	    strcpy(buf, "alias ");
	    switch (lm->major) {
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
	        switch (lm->minor) {
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
