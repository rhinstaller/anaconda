/*
 * log.c - logging functionality
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
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

#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "log.h"

static FILE * logfile = NULL;
static FILE * logfile2 = NULL;
static int loglevel = 10;

void logMessage(const char * s, ...) {
    /* JKFIXME: need to make this debugMessage and handle a level param */
    /*    if (level > loglevel) 
	  return;*/

    va_list args;

    if (logfile) {
        va_start(args, s);

        fprintf(logfile, "* ");
        vfprintf(logfile, s, args);
        fprintf(logfile, "\n");
        fflush(logfile);

        va_end(args);
    }

    if (logfile2) {
        va_start(args, s);

        fprintf(logfile2, "* ");
        vfprintf(logfile2, s, args);
        fprintf(logfile2, "\n");
        fflush(logfile2);

        va_end(args);
    }
    return;
}

void openLog(int useLocal) {
    int flags, fd;

    if (!useLocal) {
	logfile = fopen("/dev/tty3", "w");
        logfile2 = fopen("/tmp/anaconda.log", "w");
    } else {
	logfile = fopen("debug.log", "w");
    }

    if (logfile) {
        fd = fileno(logfile);
        flags = fcntl(fd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(fd, F_SETFD, flags);
    }

    if (logfile2) {
        fd = fileno(logfile2);
        flags = fcntl(fd, F_GETFD, 0) | FD_CLOEXEC;
        fcntl(fd, F_SETFD, flags);
    }
}

void closeLog(void) {
    if (logfile)
	fclose(logfile);

    if (logfile2)
	fclose(logfile2);
}

/* set the level.  higher means you see more verbosity */
void setLogLevel(int level) {
    loglevel = level;
}
