/*
 * fwloader.c -- a small firmware loader.
 *
 * Copyright (C) 2006, 2007  Red Hat, Inc.  All rights reserved.
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
 * Author(s): Peter Jones (pjones@redhat.com)
 */

#define _GNU_SOURCE 1

#include <argz.h>
#include <envz.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/poll.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <asm/types.h>
#include <linux/netlink.h>

#include "../isys/log.h"

#include "loader.h"
#include "fwloader.h"
#include "udelay.h"

#ifndef FWDEBUG
#define logMessage(x, ...)
#endif

struct fw_loader {
    int netlinkfd;
    sigset_t sigmask;
    char *fw_pathz;
    size_t fw_pathz_len;
    struct pollfd *fds;
};

int done = 0;

static inline int set_fd_coe(int fd, int enable)
{
    int rc;
    long flags = 0;

    rc = fcntl(fd, F_GETFD, &flags);
    if (rc < 0)
        return rc;

    if (enable)
        flags |= FD_CLOEXEC;
    else
        flags &= ~FD_CLOEXEC;

    rc = fcntl(fd, F_SETFD, flags);
    return rc;
}

static int open_uevent_socket(struct fw_loader *fwl)
{
    int fd, rc;
    struct sockaddr_nl sa;

    fd = socket(PF_NETLINK, SOCK_DGRAM, NETLINK_KOBJECT_UEVENT);
    if (fd < 0)
        return -1;
    set_fd_coe(fd, 1);

    memset(&sa, '\0', sizeof (sa));
    sa.nl_family = AF_NETLINK;
    sa.nl_pid = getpid();
    sa.nl_groups = -1;

    if (bind(fd, (struct sockaddr *)&sa, sizeof (sa)) < 0) {
        close(fd);
        return -1;
    }

    fwl->netlinkfd = fd;

    fd = open("/proc/sys/kernel/hotplug", O_RDWR);
    if (fd >= 0) {
        rc = ftruncate(fd, 0);
        rc = write(fd, "\n", 1);
        close(fd);
    }

    fd = open("/sys/class/firmware/timeout", O_RDWR);
    if (fd >= 0) {
        rc = write(fd, "10", 2);
        close(fd);
    }

    return 0;
}

extern void loaderSegvHandler(int signum);

static void kill_hotplug_signal(int signum)
{
    signal(signum, kill_hotplug_signal);
    logMessage(DEBUGLVL, "fwloader: got exit signal, quitting");
    done = 1;
}

static int daemonize(struct fw_loader *fwl)
{
    int fd;
    int rc;

    signal(SIGTERM, kill_hotplug_signal);
    signal(SIGSEGV, loaderSegvHandler);
    signal(SIGTTOU, SIG_IGN);
    signal(SIGTTIN, SIG_IGN);
    signal(SIGTSTP, SIG_IGN);

    sigfillset(&fwl->sigmask);
    sigdelset(&fwl->sigmask, SIGTERM);
    sigdelset(&fwl->sigmask, SIGSEGV);
    sigemptyset(&fwl->sigmask);

    prctl(PR_SET_NAME, "hotplug", 0, 0, 0);
    rc = chdir("/");

    fd = open("/proc/self/oom_adj", O_RDWR);
    if (fd >= 0) {
        rc = write(fd, "-17", 3);
        close(fd);
    }

    for (fd = 0; fd < getdtablesize(); fd++) {
        if (fd == STDIN_FILENO || fd == STDOUT_FILENO || fd == STDERR_FILENO)
            continue;
        if (fd == tty_logfd || fd == file_logfd)
            continue;
        close(fd);
    }

    setsid();
    fd = open("/dev/null", O_RDONLY);
    close(STDIN_FILENO);
    dup2(fd, STDIN_FILENO);
    set_fd_coe(STDIN_FILENO, 1);
    close(fd);
    fd = open("/dev/null", O_WRONLY);
    close(STDOUT_FILENO);
    dup2(fd, STDOUT_FILENO);
    set_fd_coe(STDOUT_FILENO, 1);
    close(STDERR_FILENO);
    dup2(fd, STDERR_FILENO);
    set_fd_coe(STDERR_FILENO, 1);
    close(fd);

    logMessage(DEBUGLVL, "fwloader: starting up (pid %d)", getpid());
    return 0;
}

struct uevent {
    char *msg;
    char *path;
    char *envz;
    size_t envz_len;
};

static int get_netlink_msg(struct fw_loader *fwl, struct uevent *uevent)
{
    size_t len;
    ssize_t size;
    static char buffer[2560];
    char *pos;
    char *msg = NULL, *path = NULL, *envz = NULL;
    char *argv[] = { NULL };
    size_t envz_len;
    error_t errnum;

    size = recv(fwl->netlinkfd, &buffer, sizeof (buffer), 0);
    if (size < 0)
        return -1;

    if ((size_t)size > sizeof (buffer) - 1)
        size = sizeof (buffer) - 1;
    buffer[size] = '\0';

    len = strcspn(buffer, "@");
    if (!buffer[len])
        return -1;

    if ((errnum = argz_create(argv, &envz, &envz_len)) > 0)
        goto err;

    pos = buffer;
    msg = strndup(pos, len++);
    pos += len;
    path = strdup(pos);

    pos += strlen(pos) + 1;
    if (len < size + 1) {
        while (pos[0]) {
            char *value = strchr(pos, '=');
            if (value)
                *(value++) = '\0';

            if ((errnum = envz_add(&envz, &envz_len, pos, value)) > 0)
                goto err;
            pos += strlen(pos) + 1;
            if (*pos)
                pos += strlen(pos) + 1;
        }
    }

    uevent->msg = msg;
    uevent->path = path;
    uevent->envz = envz;
    uevent->envz_len = envz_len;
    return 0;
err:
    if (msg)
        free(msg);
    if (path)
        free(path);
    while(envz)
        argz_delete(&envz, &envz_len, envz);
    errno = errnum;
    return -1;
}

/* Set the 'loading' attribute for a firmware device.
 * 1 == currently loading
 * 0 == done loading
 * -1 == error
 */
static int
get_loading_fd(const char *device)
{
    int fd = -1;
    char *loading_path = NULL;

    if (asprintf(&loading_path, "%s/loading", device) < 0) {
        logMessage(ERROR, "fwloader: device %s: asprintf: %m", device);
        return -1;
    }
    logMessage(DEBUGLVL, "fwloader: looking for loading file at %s", loading_path);
    fd = open(loading_path, O_RDWR | O_SYNC );
    if (fd < 0)
        logMessage(ERROR, "fwloader: open %s: %m", loading_path);
    free(loading_path);
    return fd;
}

static int
set_loading(int fd, int value)
{
    int rc = 0;

    if (value == -1)
        rc = write(fd, "-1", 3);
    else if (value == 0)
        rc = write(fd, "0", 2);
    else if (value == 1)
        rc = write(fd, "1", 2);
    fsync(fd);
    fdatasync(fd);

    return rc < 0 ? rc : 0;
}

static int
fd_map(int fd, char **buf, size_t *bufsize)
{
    struct stat stats;
    int en = 0;

    if (fstat(fd, &stats) < 0) {
        en = errno;
        close(fd);
        errno = en;
        return -1;
    }

    *buf = mmap(NULL, stats.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (*buf == MAP_FAILED) {
        *buf = NULL;
        en = errno;
        close(fd);
        errno = en;
        return -1;
    }
    *bufsize = stats.st_size;
    return 0;
}

static int
file_map(const char *filename, char **buf, size_t *bufsize, int flags)
{
    int fd, en, rc = 0;

    if ((fd = open(filename, flags ? flags : O_RDONLY)) < 0)
        return -1;

    if (fd_map(fd, buf, bufsize) < 0)
        rc = -1;

    en = errno;
    close(fd);
    errno = en;

    return rc;
}

static void
file_unmap(void *buf, size_t bufsize)
{
    munmap(buf, bufsize);
}

static int
fetcher(char *inpath, int outfd)
{
    char *inbuf = NULL;
    size_t inlen;
    int count;
    int en = 0;
    int rc;

    errno = 0;
    if (access(inpath, F_OK))
        goto out;

    if (file_map(inpath, &inbuf, &inlen, O_RDONLY) < 0)
        goto out;

    lseek(outfd, 0, SEEK_SET);
    rc = ftruncate(outfd, 0);
    rc = ftruncate(outfd, inlen);

    count = 0;
    while (count < inlen) {
        ssize_t c;
        c = write(outfd, inbuf + count, inlen - count);
        if (c <= 0)
            goto out;
        count += c;
    }

out:
    en = errno;
    if (inbuf)
        file_unmap(inbuf, inlen);
    if (en) {
        errno = en;
        return -1;
    }
    return 0;
}


static int
_load_firmware(struct fw_loader *fwl, int fw_fd, char *sysdir, int timeout)
{
    int rc = 0;
    char *fw_buf = NULL, *data = NULL;
    size_t fw_len = 0;
    int dfd = -1, lfd = -1;
    int loading = -2;
    size_t count;

    logMessage(DEBUGLVL, "fwloader: waiting for firmware dir at %s", sysdir);
    timeout *= 1000000;
    while (access(sysdir, F_OK) && timeout) {
        udelay(100);
        timeout -= 100;
    }
    if (!timeout) {
        logMessage(ERROR, "fwloader: never found firmware dir at %s", sysdir);
        return -ENOENT;
    }

    if ((lfd = get_loading_fd(sysdir)) < 0)
        return lfd;

    set_loading(lfd, 1);
    loading = -1;

    if (fd_map(fw_fd, &fw_buf, &fw_len) < 0) {
        rc = -errno;
        goto out;
    }

    if (asprintf(&data, "%s/data", sysdir) < 0) {
        rc = -errno;
        goto out;
    }
    if ((dfd = open(data, O_RDWR)) < 0) {
        rc = -errno;
        goto out;
    }
    count = 0;
    while (count < fw_len) {
        ssize_t c;
        if ((c = write(dfd, fw_buf + count, fw_len - count)) <= 0)
            goto out;
        count += c;
    }
    loading = 0;

out:
    if (dfd >= 0)
        close(dfd);
    if (fw_buf)
        file_unmap(fw_buf, fw_len);
    if (loading != -2)
        set_loading(lfd, loading);
    if (lfd >= 0)
        close(lfd);
    if (data)
        free(data);

    return rc;
}

static void load_firmware(struct fw_loader *fwl, struct uevent *uevent)
{
    char *devpath = NULL, *firmware = NULL, *timeout;
    char *fw_file = NULL, *sys_file = NULL;
    char *entry;
    int timeout_secs;
    char *tempfile;
    int fd = -1;

    tempfile = strdup("/tmp/fw-XXXXXX");
    fd = mkstemp(tempfile);
    if (fd < 0) {
        logMessage(ERROR, "fwloader: mkstemp(\"%s\") failed: %m", tempfile);
        free(tempfile);
        return;
    }
    unlink(tempfile);
    free(tempfile);

    devpath = envz_get(uevent->envz, uevent->envz_len, "DEVPATH");
    firmware = envz_get(uevent->envz, uevent->envz_len, "FIRMWARE");
    timeout = envz_get(uevent->envz, uevent->envz_len, "TIMEOUT");
    
    if (!devpath || !firmware) {
        argz_stringify(uevent->envz, uevent->envz_len, ' ');
        logMessage(ERROR, "fwloader: environment: %s", uevent->envz);
        return;
    }

    errno = 0;
    timeout_secs = strtol(timeout, NULL, 10);

    if ((errno == ERANGE && (timeout_secs == LONG_MIN ||
                             timeout_secs == LONG_MAX)) ||
        (errno != 0 && timeout_secs == 0)) {
        logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    /* find the file */
    for (entry = fwl->fw_pathz; entry;
            entry = argz_next(fwl->fw_pathz, fwl->fw_pathz_len, entry)) {
        if (asprintf(&fw_file, "%s/%s", entry, firmware) < 0)
            return;

        logMessage(INFO, "fwloader: trying to find %s at %s", firmware, fw_file);

        if (fetcher(fw_file, fd) >= 0)
            break;

        free(fw_file);
        fw_file = NULL;
        if (errno == ENOENT || errno == EPERM)
            continue;
        break;
    }
    if (!fw_file)
        goto out;

    if (asprintf(&sys_file, "/sys%s/", devpath) < 0)
        goto out;

    _load_firmware(fwl, fd, sys_file, timeout_secs);

out:
    if (fw_file)
        free(fw_file);
    if (sys_file)
        free(sys_file);
    if (fd != -1)
        close(fd);
}

static void handle_single_uevent(struct fw_loader *fwl, struct uevent *uevent)
{
    char *action = NULL;
    char *subsystem = NULL;

    action = envz_get(uevent->envz, uevent->envz_len, "ACTION");
    subsystem = envz_get(uevent->envz, uevent->envz_len, "SUBSYSTEM");

    logMessage(DEBUGLVL, "fwloader: subsystem %s got action %s", subsystem, action);
    if (!strcmp(action, "add") && !strcmp(subsystem, "firmware"))
        load_firmware(fwl, uevent);
}

static void handle_events(struct fw_loader *fwl)
{
    int rc;
    struct uevent uevent;
    if (fwl->fds == NULL)
        fwl->fds = calloc(1, sizeof (struct pollfd));

    do {
        do {
            if (done)
                exit(0);
            fwl->fds[0].events = POLLIN | POLLPRI;
            fwl->fds[0].revents = 0;
            fwl->fds[0].fd = fwl->netlinkfd;

            //logMessage(DEBUGLVL, "fwloader: polling on netlink socket");
            errno = 0;
            rc = poll(fwl->fds, 1, -1);
            //logMessage(DEBUGLVL, "fwloader: poll returned %d", rc);

            if (done)
                exit(0);
        } while (rc < 1 || (rc < 0 && errno == EINTR));

        memset(&uevent, '\0', sizeof (uevent));
        if (get_netlink_msg(fwl, &uevent) < 0)
            continue;

        handle_single_uevent(fwl, &uevent);
    } while (1);

    if (fwl->fds) {
        free(fwl->fds);
        fwl->fds = NULL;
    }
}

void set_fw_search_path(struct loaderData_s *loaderData, char *path)
{
    char *old = loaderData->fw_search_pathz, *new = NULL;
    size_t old_len = loaderData->fw_search_pathz_len;

    loaderData->fw_search_pathz = NULL;
    loaderData->fw_search_pathz_len = -1;
    if (!path) {
        if (old)
            free(old);
        return;
    }

    if ((new = strdup(path)) == NULL)
        goto out;

    loaderData->fw_search_pathz = NULL;
    loaderData->fw_search_pathz_len = 0;
    if (argz_create_sep(new, ':', &loaderData->fw_search_pathz,
                &loaderData->fw_search_pathz_len) != 0)
        goto out;

    if (old)
        free(old);

    return;
out:
    if (new)
        free(new);
    loaderData->fw_search_pathz = old;
    loaderData->fw_search_pathz_len = old_len;

    return;
}

void add_fw_search_dir(struct loaderData_s *loaderData, char *dir)
{
    argz_add(&loaderData->fw_search_pathz, &loaderData->fw_search_pathz_len,
            dir);
}

void do_fw_loader(struct loaderData_s *loaderData)
{
    struct fw_loader fwl;
    int rc;

    memset(&fwl, '\0', sizeof (fwl));
    fwl.netlinkfd = -1;

    fwl.fw_pathz = loaderData->fw_search_pathz;
    fwl.fw_pathz_len = loaderData->fw_search_pathz_len;

    logMessage(INFO, "fwloader: starting firmware loader");

    rc = daemonize(&fwl);
    if (rc < 0) {
        logMessage(ERROR, "fwloader: daemonize() failed with %d: %m", rc);
        exit(1);
    }

    if (open_uevent_socket(&fwl) < 0) {
        logMessage(ERROR, "fwloader: open_uevent_socket() failed: %m");
        exit(1);
    }

    logMessage(DEBUGLVL, "fwloader: entering event loop");
    handle_events(&fwl);

    exit(1);
}


void start_fw_loader(struct loaderData_s *loaderData) {
    pid_t loader;

    loader = fork();
    if (loader > 0)
        loaderData->fw_loader_pid = loader;
    if (loader != 0)
        return;
    
    do_fw_loader(loaderData);
}

void stop_fw_loader(struct loaderData_s *loaderData) {
    int x = 0, rc;
    siginfo_t siginfo;
    if (loaderData->fw_loader_pid > 0)
        kill(loaderData->fw_loader_pid, SIGTERM);
    while (x <= 100) {
        if (x > 90)
            kill(loaderData->fw_loader_pid, SIGKILL);
        memset(&siginfo, '\0', sizeof (siginfo));
        rc = waitid(P_PID, loaderData->fw_loader_pid, &siginfo, WNOHANG|WEXITED);
        if (rc < 0 && errno == ECHILD)
            return;
        else if (rc == 0 && siginfo.si_pid != 0)
            return;
        else if (rc == 0)
            x++;
        usleep(10000);
    }
    return;
}


/*
 * vim:ts=8:sw=4:sts=4:et
 */
