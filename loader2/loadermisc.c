/*
 * loadermisc.c - miscellaneous loader functions that don't seem to fit
 * anywhere else (yet)  (was misc.c)
 * JKFIXME: need to break out into reasonable files based on function
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
#include <string.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdlib.h>

#include "log.h"

int copyFileFd(int infd, char * dest) {
    int outfd;
    char buf[4096];
    int i;
    int rc = 0;

    outfd = open(dest, O_CREAT | O_RDWR, 0666);

    if (outfd < 0) {
	logMessage("failed to open %s: %s", dest, strerror(errno));
	return 1;
    }

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
	if (write(outfd, buf, i) != i) {
	    rc = 1;
	    break;
	}
    }

    close(outfd);

    return rc;
}

int copyFile(char * source, char * dest) {
    int infd = -1;
    int rc;

    infd = open(source, O_RDONLY);

    if (infd < 0) {
	logMessage("failed to open %s: %s", source, strerror(errno));
	return 1;
    }

    rc = copyFileFd(infd, dest);

    close(infd);

    return rc;
}

char * readLine(FILE * f) {
    char buf[1024];

    fgets(buf, sizeof(buf), f);

    /* chop */
    buf[strlen(buf) - 1] = '\0';

    return strdup(buf);
}

int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);

    return strcmp(first, second);
}

char * sdupprintf(const char *format, ...) {
    char *buf = NULL;
    char c;
    va_list args;
    size_t size = 0;

    va_start(args, format);
    
    /* XXX requires C99 vsnprintf behavior */
    size = vsnprintf(&c, 1, format, args) + 1;
    if (size == -1) {
	printf("ERROR: vsnprintf behavior is not C99\n");
	abort();
    }

    va_end(args);
    va_start(args, format);

    buf = malloc(size);
    if (buf == NULL)
	return NULL;
    vsnprintf(buf, size, format, args);
    va_end (args);

    return buf;
}


/* look for available memory.  note: won't ever report more than the 
 * 900 megs or so supported by the -BOOT kernel due to not using e820 */
int totalMemory(void) {
    int fd;
    int bytesRead;
    char buf[4096];
    char * chptr, * start;
    int total = 0;
    
    fd = open("/proc/meminfo", O_RDONLY);
    if (fd < 0) {
        logMessage("failed to open /proc/meminfo: %s", strerror(errno));
        return 0;
    }
    
    bytesRead = read(fd, buf, sizeof(buf) - 1);
    if (bytesRead < 0) {
        logMessage("failed to read from /proc/meminfo: %s", strerror(errno));
        close(fd);
        return 0;
    }
    
    close(fd);
    buf[bytesRead] = '\0';
    
    chptr = buf;
    while (*chptr && !total) {
        if (strncmp(chptr, "MemTotal:", 9)) {
            chptr++;
            continue;
        }

        start = ++chptr ;
        while (*chptr && *chptr != '\n') chptr++;

        *chptr = '\0';
    
        while (!isdigit(*start) && *start) start++;
        if (!*start) {
            logMessage("no number appears after MemTotal tag");
            return 0;
        }

        chptr = start;
        while (*chptr && isdigit(*chptr)) {
            total = (total * 10) + (*chptr - '0');
            chptr++;
        }
    }

    logMessage("%d kB are available", total);
    
    return total;
}
