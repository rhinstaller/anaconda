/*
 * moduledeps.c - module dependency determination
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

#include "moduledeps.h"

moduleDeps mlNewDeps(void) {
    moduleDeps md;

    md = malloc(sizeof(*md));
    md->name = NULL;
    md->deps = NULL;

    return md;
}

/* JKFIXME: if we have a new module with different deps, this doesn't
 * handle it correctly */
int mlLoadDeps(moduleDeps * moduleDepListPtr, const char * path) {
    int fd;
    char * buf;
    struct stat sb;
    char * start, * end, * chptr;
    int i, numItems;
    moduleDeps nextDep;
    moduleDeps moduleDepList = *moduleDepListPtr;
    int ret;

    fd = open(path, O_RDONLY);
    if (fd < 0) {
        return -1;
    }

    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    ret = read(fd, buf, sb.st_size);
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

    /* We have to remove `\' first. */
    start = buf;
    start = strchr(start, '\\');
    while (start) {
	/* Replace `\\' with a space. */
	*start++ = ' ';
	/* Replace the following `\n' and `\r' with a space. */
        if (*start == '\n') {
	    *start++ = ' ';
            if (*start == '\r')
                *start++ = ' ';
	}
	else if (*start == '\r') {
            *start++ = ' ';
            if (*start == '\n')
                *start++ = ' ';
        }
	start = strchr(start, '\\');

    }

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
    
    for (dep = modDeps; dep && dep->name && strcmp(dep->name, modName); dep++);

    if (dep) return dep->deps;

    return NULL;
}

/* fun test cases... */
#ifdef TESTING

void printDeps(moduleDeps modDeps) {
    moduleDeps dep;
    char buf[1024];
    char **foo;

    for (dep = modDeps; dep && dep->name; dep++) {
        if (strcmp(dep->name, "pcnet32"))
            continue;
        if (!dep->deps)
            printf("module: %s, no deps\n", dep->name);
        else {
            buf[0] = '\0';
            for (foo = dep->deps; *foo; foo++) {
                strcat(buf, *foo); 
                strcat(buf, " ");
            }
            printf("module: %s, deps: %s\n", dep->name, buf);
        }
    }
}

int main(int argc, char ** argv) {
    moduleDeps deps;

    deps = mlNewDeps();
    printDeps(deps);
    mlLoadDeps(&deps, "modules.dep.1");
    printDeps(deps);

    printf("----------------------------------------\n");
    printf("Loading second set\n");
    mlLoadDeps(&deps, "modules.dep.2");
    printDeps(deps);

    return 0;
}
#endif
