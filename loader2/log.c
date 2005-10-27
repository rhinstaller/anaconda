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
#include <time.h>
#include <unistd.h>

#include "log.h"

static FILE * logfile = NULL;
static FILE * logfile2 = NULL;
static int minLevel = WARNING;

static void printLogHeader(int level, FILE *outfile) {
    time_t current_time = time(NULL);
    struct tm *t = gmtime (&current_time);

    switch (level) {
        case DEBUGLVL:
            fprintf (outfile, "%02d:%02d:%02d DEBUG   : ", t->tm_hour,
                     t->tm_min, t->tm_sec);
            break;

        case INFO:
            fprintf (outfile, "%02d:%02d:%02d INFO    : ", t->tm_hour,
                     t->tm_min, t->tm_sec);
            break;

        case WARNING:
            fprintf (outfile, "%02d:%02d:%02d WARNING : ", t->tm_hour,
                     t->tm_min, t->tm_sec);
            break;

        case ERROR:
            fprintf (outfile, "%02d:%02d:%02d ERROR   : ", t->tm_hour,
                     t->tm_min, t->tm_sec);
            break;

        case CRITICAL:
            fprintf (outfile, "%02d:%02d:%02d CRITICAL: ", t->tm_hour,
                     t->tm_min, t->tm_sec);
            break;
    }
}

void logMessage(int level, const char * s, ...) {
    va_list args;

    if (level < minLevel) 
        return;

    if (logfile) {
        va_start(args, s);

        printLogHeader(level, logfile);
        vfprintf(logfile, s, args);
        fprintf(logfile, "\n");
        fflush(logfile);

        va_end(args);
    }

    if (logfile2) {
        va_start(args, s);

        printLogHeader(level, logfile2);
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
    minLevel = level;
}
