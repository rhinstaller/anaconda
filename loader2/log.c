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
static int logfd;
static int loglevel = 10;

static FILE * logfile2 = NULL;
static int logfd2 = 0;

void logMessage(const char * s, ...) {
    /* JKFIXME: need to make this debugMessage and handle a level param */
    /*    if (level > loglevel) 
	  return;*/

    va_list args;

    if (!logfile) return;

    va_start(args, s);

    fprintf(logfile, "* ");
    vfprintf(logfile, s, args);
    fprintf(logfile, "\n");
    fflush(logfile);

    va_end(args);

    if (!logfile2) return;

    va_start(args, s);

    fprintf(logfile2, "* ");
    vfprintf(logfile2, s, args);
    fprintf(logfile2, "\n");
    fflush(logfile2);

    va_end(args);

    return;
}

void openLog(int useLocal) {
    if (!useLocal) {
	logfile = fopen("/dev/tty3", "w");
	if (logfile) {
	    logfd = open("/dev/tty3", O_WRONLY);
	    logfile2 = fopen("/tmp/anaconda.log", "w");
	    if (logfile2)
		logfd2 = open("/tmp/anaconda.log", O_WRONLY | O_APPEND);
	} else {
	    logfile = fopen("/tmp/anaconda.log", "w");
	    logfd = open("/tmp/anaconda.log", O_WRONLY| O_APPEND);
	}
    } else {
	logfile = fopen("debug.log", "w");
	logfd = open("debug.log", O_WRONLY);
    }
}

void closeLog(void) {
    if (logfile) {
	fclose(logfile);
	close(logfd);
    }
    if (logfile2) {
	fclose(logfile2);
	close(logfd2);
    }
}

/* set the level.  higher means you see more verbosity */
void setLogLevel(int level) {
    loglevel = level;
}
