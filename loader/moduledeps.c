#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "misc.h"
#include "modules.h"
#include "moduledeps.h"

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

char ** mlGetDeps(moduleDeps modDeps, const char * modName) {
    moduleDeps dep;
    
    for (dep = modDeps; dep->name && strcmp(dep->name, modName); dep++);

    if (dep) return dep->deps;

    return NULL;
}
