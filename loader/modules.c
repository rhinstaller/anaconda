#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "isys/isys.h"

#include "modules.h"

struct moduleDependency_s {
    char * name;
    char ** deps;
};

struct moduleList_s {
    char * modules[50];
    int numModules;
};

static int moduleLoaded(moduleList modList, const char * name);

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
	ml->modules[ml->numModules] = strdup(start);
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

    for (i = 0; i < ml->numModules; i++)
        free(ml->modules[i]);
    free(ml);
}

moduleDeps mlNewDeps(void) {
    moduleDeps md;

    md = malloc(sizeof(*md));
    md->name = NULL;
    md->deps = NULL;

    return md;
}

int mlLoadDeps(moduleDeps moduleDepList, const char * path) {
    int fd;
    char * buf;
    struct stat sb;
    char * start, * end, * chptr;
    int i, numItems;
    moduleDeps nextDep;

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
	i = strlen(chptr) / 3;
	nextDep->deps = malloc(sizeof(char **) * i);
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
	nextDep++;

	start = end + 1;
    }

    nextDep->name = NULL;
    nextDep->deps = NULL;
    moduleDepList = realloc(moduleDepList, sizeof(*moduleDepList) *
				(nextDep - moduleDepList + 1));

    return 0;
}

static int moduleLoaded(moduleList modList, const char * name) {
    int i;

    for (i = 0; i < modList->numModules; i++)
        if (!strcmp(modList->modules[i], name)) return 1;

    return 0;
}

int mlLoadModule(char * modName, moduleList modLoaded,
	         moduleDeps modDeps, int testing) {
    moduleDeps dep;
    char ** nextDep;
    char fileName[80];
    int rc;


    for (dep = modDeps; dep->name && strcmp(dep->name, modName);
    	 dep++);

    if (dep && dep->deps) {
	nextDep = dep->deps;
	while (*nextDep) {
	    if (!moduleLoaded(modLoaded, *nextDep)) {
		mlLoadModule(*nextDep, modLoaded, modDeps, testing);
	    }

	    nextDep++;
	}
    }

    if (testing) return 0;

    sprintf(fileName, "%s.o", modName);

    printf("loading %s\n", fileName);
    rc = insmod(fileName, NULL);
    if (!rc)
	modLoaded->modules[modLoaded->numModules++] = strdup(modName);

    return rc;
}

char ** mlGetDeps(moduleDeps modDeps, const char * modName) {
    moduleDeps dep;
    
    for (dep = modDeps; dep->name && strcmp(dep->name, modName); dep++);

    if (dep) return dep->deps;

    return NULL;
}
