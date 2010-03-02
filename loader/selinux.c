/*
 * selinux.c - Various SELinux related functionality needed for the loader.
 * Portions extracted from libselinux which was released as public domain
 * software by the NSA.
 *
 * Copyright (C) 2004  Red Hat, Inc.  All rights reserved.
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
 *
 * Author(s): Jeremy Katz <katzj@redhat.com>
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <string.h>

#include "loader.h"
#include "loadermisc.h"
#include "../isys/log.h"

int loadpolicy() {
    int pid, status;

    logMessage(INFO, "Loading SELinux policy");

    if (!(pid = fork())) {
        setenv("LD_LIBRARY_PATH", LIBPATH, 1);
        execl("/sbin/load_policy",
              "/sbin/load_policy", "-q", NULL);
        logMessage(ERROR, "exec of load_policy failed: %m");
        exit(1);
    }

    waitpid(pid, &status, 0);
    if (WIFEXITED(status) && (WEXITSTATUS(status) != 0))
        return 1;

    return 0;
}

