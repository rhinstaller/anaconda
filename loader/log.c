#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "log.h"

static FILE * logfile = NULL;
static int logfd;
#if 0
static int logDebugMessages = 0;
#endif

static void doLogMessage(const char * s, va_list args);

void logMessage(const char * s, ...) {
    va_list args;

    if (!logfile) return;

    va_start(args, s);

    fprintf(logfile, "* ");
    vfprintf(logfile, s, args);
    fprintf(logfile, "\n");
    fflush(logfile);

    va_end(args);

    return;
}

void openLog(int useLocal) {
    if (!useLocal) {
	logfile = fopen("/dev/tty3", "w");
	if (logfile)
	    logfd = open("/dev/tty3", O_WRONLY);
	else {
	    logfile = fopen("/tmp/install.log", "w");
	    logfd = open("/tmp/install.log", O_WRONLY| O_APPEND);
	}
    } else {
	logfile = fopen("debug.log", "w");
	logfd = open("debug.log", O_WRONLY);
    }
#if 0
    if (getenv("DEBUG")) logDebugMessages = 1;
#endif
}

void closeLog(void) {
    if (logfile) {
	fclose(logfile);
	close(logfd);
    }
}

