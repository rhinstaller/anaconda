/*
 * shutdown.c
 *
 * Shutdown a running system.  If built with -DAS_SHUTDOWN=1, then
 * it builds a standalone shutdown binary.
 *
 * Copyright (C) 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/reboot.h>
#include <sys/types.h>
#include <unistd.h>

#include "init.h"

void disableSwap(void);
void unmountFilesystems(void);

static void performTerminations(int doKill) {
	if (!doKill)
		return;

	sync();
	printf("sending termination signals...");
	kill(-1, 15);
	sleep(2);
	printf("done\n");

	printf("sending kill signals...");
	kill(-1, 9);
	sleep(2);
	printf("done\n");
}

static void performUnmounts(int doKill) {
	int ignore;

	if (!doKill)
		return;

	printf("disabling swap...\n");
	disableSwap();

	printf("unmounting filesystems...\n"); 
	unmountFilesystems();

	printf("waiting for mdraid sets to become clean...\n"); 
	ignore = system("/sbin/mdadm --wait-clean --scan");
}

static void performReboot(reboot_action rebootAction) {
	if (rebootAction == POWEROFF) {
        printf("powering off system\n");
		sleep(2);
        reboot(RB_POWER_OFF);
	} else if (rebootAction == REBOOT) {
		printf("rebooting system\n");
		sleep(2);

#if USE_MINILIBC
		reboot(0xfee1dead, 672274793, 0x1234567);
#else
		reboot(RB_AUTOBOOT);
#endif
	}
}

int shouldReboot = 0;

static void rebootHandler(int signum) {
    shouldReboot = 1;
}

void shutDown(int doKill, reboot_action rebootAction) {
	if (rebootAction == POWEROFF || rebootAction == REBOOT) {
		performUnmounts(doKill);
		performTerminations(doKill);
		if (doKill)
			performReboot(rebootAction);
	}

	if (!shouldReboot && rebootAction != REBOOT)
		printf("you may safely reboot your system\n");
	
    signal(SIGINT, rebootHandler);
	while (1) {
		if (shouldReboot) {
			performUnmounts(1);
			performTerminations(1);
			performReboot(REBOOT);
		}
		sleep(1);
	}

    exit(0);

    return;
}

#ifdef AS_SHUTDOWN
int main(int argc, char ** argv) {
    int fd;
    reboot_action rebootAction = HALT;
    int doKill = 1;
    int i = 1;

    while (i < argc) {
      if (!strncmp("-r", argv[i], 2))
        rebootAction = REBOOT;
      else if (!strncmp("--nokill", argv[i], 8))
        doKill = 0;
      else if (!strncmp("-P", argv[i], 2))
        rebootAction = POWEROFF;
      i++;
    }

    /* ignore some signals so we don't kill ourself */
    signal(SIGINT, SIG_IGN);
    signal(SIGTSTP, SIG_IGN);

    /* now change to / */
    i = chdir("/");

    /* redirect output to the real console */
    fd = open("/dev/console", O_RDWR);
    dup2(fd, 0);
    dup2(fd, 1);
    dup2(fd, 2);
    close(fd);

    shutDown(doKill, rebootAction);
    return 0;
}
#endif

/* vim:set shiftwidth=4 softtabstop=4 ts=4: */
