/* Newvc - run a program in another virtual console */

/* Copyright (C) 1992 by MAEDA Atusi (mad@math.keio.ac.jp) */
/* Version 0.1 92/1/11 */
/* Version 0.2 92/1/19 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <limits.h>
#include <pwd.h>
#include <utmp.h>
#include <time.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/kd.h>
#include <sys/vt.h>
#include <sys/wait.h>

#define MAXTTYLEN 12

#define MAXCMDLEN 4096

char cmdBuf[MAXCMDLEN];

char *progName;
char newTtyName[MAXTTYLEN];

void error(const char *message, const char *perrorMessage) {
    fprintf(stderr, "%s: %s\n", progName, message);
    if (perrorMessage) {
	perror(perrorMessage);
    }
    exit(EXIT_FAILURE);
}

struct passwd *pw;
struct utmp ut;

void setUtmpEntry(int pid) {

    pw = getpwuid(getuid());
    setutent();				 /* open utmp */
    strncpy(ut.ut_id, newTtyName + strlen("/dev/tty"), sizeof(ut.ut_id));
    ut.ut_type = DEAD_PROCESS;
    getutid(&ut);			 /* set position */
    /* Set up the new entry. */
    ut.ut_type = USER_PROCESS;
    strncpy(ut.ut_line, newTtyName + strlen("/dev/"), sizeof(ut.ut_line));
    strncpy(ut.ut_user, (pw && pw->pw_name) ? pw->pw_name : "????",
	    sizeof(ut.ut_user));
/*
    gethostname(ut.ut_host, sizeof(ut.ut_host));
*/
    ut.ut_pid = pid;
    ut.ut_time = time(NULL);
    pututline(&ut);
    endutent();				 /* close utmp */
}

void restoreUtmpEntry(int pid) {
    struct utmp *utp;

    pw = getpwuid(getuid());
    setutent();				 /* open utmp */
    strncpy(ut.ut_id, newTtyName + strlen("/dev/tty"), sizeof(ut.ut_id));
    ut.ut_type = USER_PROCESS;
    utp = getutid(&ut);			 /* search entry */
    /* Set up the new entry. */
    if (utp && utp->ut_pid == pid) {
	ut.ut_type = DEAD_PROCESS;
	ut.ut_time = time(NULL);
	pututline(&ut);
    }
    endutent();				 /* close utmp */
}

int main(int argc, char* argv[]) {
    int	curVcNum, newVcNum;
    int consoleFd = 0;
    int newVcFd;
    int childPid;
    struct vt_stat vts;

    progName = argv[0];

    if ((consoleFd = open("/dev/console", 0)) < 0) {
	    error("can't open console", "/dev/console");
    }

    ioctl(consoleFd, VT_GETSTATE, &vts);
    curVcNum = vts.v_active;

    ioctl(consoleFd, VT_OPENQRY, &newVcNum);
    if (newVcNum < 0) {
	error("can't find unused virtual console", NULL);
    }
    sprintf(newTtyName, "/dev/tty%d", newVcNum);

    setsid();
    
    if ((newVcFd = open(newTtyName, O_RDWR)) < 0) {
	error("can't open virtual console", newTtyName);
    }
    if (ioctl(consoleFd, VT_ACTIVATE, newVcNum) != 0) {
	error("can't switch virtual console", "ioctl VT_ACTIVATE");
    }

    dup2(newVcFd, 0);
    dup2(newVcFd, 1);
    dup2(newVcFd, 2);

    if ((childPid = fork()) < 0) {
	error("fork failed", "fork");
    }
    if (childPid) {
	/* Parent process. */
	int status;

	setUtmpEntry(childPid);

	wait(&status);

	restoreUtmpEntry(childPid);

	if (ioctl(0, VT_ACTIVATE, curVcNum) != 0) {
	    error("couldn't restore original console", "ioctl(0, VT_ACTIVATE)");
	}
	return WEXITSTATUS(status);
    } else {
	/* Child process. */
	char *shell, *command;
	char *newArgv[] = {"/bin/sh", "-c", cmdBuf, NULL};

	setuid(getuid());
	setgid(getgid());

	if ((shell = getenv("SHELL")) == NULL) {
	    shell = "/bin/sh";
	}
	if (argc == 1) {
	    /* No command specified.  Run shell as default. */
	    if ((command = rindex(shell, '/')) == NULL) {
		command = shell;
	    } else {
		command++;
	    }
	    newArgv[1] = NULL;
	} else {
	    int i;

	    command = argv[1];
	    for (i = 1; i < argc; i++) {
		strncat(cmdBuf, argv[i], MAXCMDLEN);
		strncat(cmdBuf, " ", MAXCMDLEN);
	    }
	}
	newArgv[0] = command;

	execv(shell, newArgv);

	error("can't exec", shell);

	return EXIT_FAILURE;
    }
}
