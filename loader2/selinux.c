/*
 * selinux.c - Various SELinux related functionality needed for the loader.
 *
 * Jeremy Katz <katzj@redhat.com>
 * 
 * Copyright 2004 Red Hat, Inc.
 * Portions extracted from libselinux which was released as public domain
 *   software by the NSA.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
#include "log.h"

int loadpolicy() {
    int pid, status;

    logMessage(INFO, "Loading SELinux policy");

    if (!(pid = fork())) {
        setenv("LD_LIBRARY_PATH", LIBPATH, 1);
        execl("/usr/sbin/load_policy", 
              "/usr/sbin/load_policy", "-q", "-b", NULL);
        logMessage(ERROR, "exec of load_policy failed: %s", strerror(errno));
        exit(1);
    }

    waitpid(pid, &status, 0);
    if (WIFEXITED(status) && (WEXITSTATUS(status) != 0))
        return 1;

    return 0;
}

