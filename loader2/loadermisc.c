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
	logMessage(ERROR, "failed to open %s: %s", dest, strerror(errno));
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
	logMessage(ERROR, "failed to open %s: %s", source, strerror(errno));
	return 1;
    }

    rc = copyFileFd(infd, dest);

    close(infd);

    return rc;
}

char * readLine(FILE * f) {
    char buf[1024], *ret;

    ret = fgets(buf, sizeof(buf), f);

    /* chop */
    buf[strlen(buf) - 1] = '\0';

    return strdup(buf);
}

/* FIXME: when we only depend on glibc, we could use strvercmp instead */
/* compare alpha and numeric segments of two versions */
/* return 1: a is newer than b */
/*        0: a and b are the same version */
/*       -1: b is newer than a */
static int rpmvercmp(const char * a, const char * b)
{
    char oldch1, oldch2;
    char * str1, * str2;
    char * one, * two;
    int rc;
    int isnum;

    /* easy comparison to see if versions are identical */
    if (!strcmp(a, b)) return 0;

    str1 = alloca(strlen(a) + 1);
    str2 = alloca(strlen(b) + 1);

    strcpy(str1, a);
    strcpy(str2, b);

    one = str1;
    two = str2;

    /* loop through each version segment of str1 and str2 and compare them */
    while (*one && *two) {
	while (*one && !isalnum(*one)) one++;
	while (*two && !isalnum(*two)) two++;

	str1 = one;
	str2 = two;

	/* grab first completely alpha or completely numeric segment */
	/* leave one and two pointing to the start of the alpha or numeric */
	/* segment and walk str1 and str2 to end of segment */
	if (isdigit(*str1)) {
	    while (*str1 && isdigit(*str1)) str1++;
	    while (*str2 && isdigit(*str2)) str2++;
	    isnum = 1;
	} else {
	    while (*str1 && isalpha(*str1)) str1++;
	    while (*str2 && isalpha(*str2)) str2++;
	    isnum = 0;
	}

	/* save character at the end of the alpha or numeric segment */
	/* so that they can be restored after the comparison */
	oldch1 = *str1;
	*str1 = '\0';
	oldch2 = *str2;
	*str2 = '\0';

	/* take care of the case where the two version segments are */
	/* different types: one numeric, the other alpha (i.e. empty) */
	if (one == str1) return -1;	/* arbitrary */
	/* XXX See patch #60884 (and details) from bugzilla #50977. */
	if (two == str2) return (isnum ? 1 : -1);

	if (isnum) {
	    /* this used to be done by converting the digit segments */
	    /* to ints using atoi() - it's changed because long  */
	    /* digit segments can overflow an int - this should fix that. */

	    /* throw away any leading zeros - it's a number, right? */
	    while (*one == '0') one++;
	    while (*two == '0') two++;

	    /* whichever number has more digits wins */
	    if (strlen(one) > strlen(two)) return 1;
	    if (strlen(two) > strlen(one)) return -1;
	}

	/* strcmp will return which one is greater - even if the two */
	/* segments are alpha or if they are numeric.  don't return  */
	/* if they are equal because there might be more segments to */
	/* compare */
	rc = strcmp(one, two);
	if (rc) return (rc < 1 ? -1 : 1);

	/* restore character that was replaced by null above */
	*str1 = oldch1;
	one = str1;
	*str2 = oldch2;
	two = str2;
    }

    /* this catches the case where all numeric and alpha segments have */
    /* compared identically but the segment sepparating characters were */
    /* different */
    if ((!*one) && (!*two)) return 0;

    /* whichever version still has characters left over wins */
    if (!*one) return -1; else return 1;
}

int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);

    return rpmvercmp(first, second);
}

char * sdupprintf(const char *format, ...) {
    char *buf = NULL;
    char c;
    va_list args;
    int size = 0;

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
        logMessage(ERROR, "failed to open /proc/meminfo: %s", strerror(errno));
        return 0;
    }
    
    bytesRead = read(fd, buf, sizeof(buf) - 1);
    if (bytesRead < 0) {
        logMessage(ERROR, "failed to read from /proc/meminfo: %s", strerror(errno));
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
            logMessage(WARNING, "no number appears after MemTotal tag");
            return 0;
        }

        chptr = start;
        while (*chptr && isdigit(*chptr)) {
            total = (total * 10) + (*chptr - '0');
            chptr++;
        }
    }

    logMessage(INFO, "%d kB are available", total);
    
    return total;
}
