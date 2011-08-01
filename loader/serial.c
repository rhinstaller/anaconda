#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>

#include <linux/serial.h>

#include <sys/ioctl.h>

#include <glib.h>

#include "../pyanaconda/isys/log.h"

#if defined(__sparc__)
static int termcmp(struct termios *a, struct termios *b) {
    if (a->c_iflag != b->c_iflag || a->c_oflag != b->c_oflag ||
    a->c_cflag != b->c_cflag || a->c_lflag != b->c_lflag)
    return 1;
    return memcmp(a->c_cc, b->c_cc, sizeof(a->c_cc));
}
#endif

#if !defined(__s390__) && !defined(__s390x__) && !defined(__sparc__)
static int termcmp(struct termios *a, struct termios *b) {
    if (a->c_iflag != b->c_iflag || a->c_oflag != b->c_oflag ||
        a->c_cflag != b->c_cflag || a->c_lflag != b->c_lflag ||
        a->c_ispeed != b->c_ispeed || a->c_ospeed != b->c_ospeed)
        return 1;
    return memcmp(a->c_cc, b->c_cc, sizeof(a->c_cc));
}
#endif

void get_mode_and_flags(struct termios *cmode, int *flags) {
    int fd;

    fd = open("/dev/console", O_RDONLY);
    tcgetattr(fd, cmode);
    *flags = fcntl(fd, F_GETFL);
    close(fd);
}

void set_mode(struct termios *cmode) {
    int fd;

    fd = open("/dev/console", O_WRONLY);
    tcsetattr(fd, TCSANOW, cmode);
    close(fd);
}

void restore_mode(struct termios *orig_cmode) {
    int fd;

    fd = open("/dev/console", O_WRONLY);
    tcsetattr(fd, TCSANOW, orig_cmode);
    close(fd);
}

void restore_flags(int orig_flags) {
    int fd;

    fd = open("/dev/console", O_WRONLY);
    fcntl(fd, F_SETFL, orig_flags);
    close(fd);
}

#if !defined(__s390__) && !defined(__s390x__)
static int serial_requested(GHashTable *cmdline) {
    if (cmdline && g_hash_table_lookup_extended(cmdline, "serial", NULL, NULL))
        return 1;
    else
        return 0;
}

static int get_serial_fd() {
    int i, fd = -1;
    int weird = 0;
    char twelve = 12;
    char *console = NULL;
    static struct serial_struct si;

    struct termios orig_cmode, cmode, mode;
    int orig_flags;

    get_mode_and_flags(&orig_cmode, &orig_flags);

    cmode = orig_cmode;
    cmode.c_lflag &= (~ECHO);

    set_mode(&cmode);

    /* handle weird consoles */
#if defined(__powerpc__)
    char * consoles[] = { "/dev/hvc0", /* hvc for JS20 */

                          "/dev/hvsi0", "/dev/hvsi1",
                          "/dev/hvsi2", /* hvsi for POWER5 */
                          NULL };
#elif defined (__i386__) || defined (__x86_64__)
    char * consoles[] = { "/dev/xvc0", "/dev/hvc0", NULL };
#else
    char * consoles[] = { NULL };
#endif
    for (i = 0; consoles[i] != NULL; i++) {
        if ((fd = open(consoles[i], O_RDWR)) >= 0 && !tcgetattr(fd, &mode) && !termcmp(&cmode, &mode)) {
            console = strdup(consoles[i]);
            logMessage(INFO, "set console to %s at %d", console, __LINE__);
            weird = 1;
            break;
        }
        close(fd);
    }

    restore_mode(&orig_cmode);

    if (fd < 0 && ioctl(0, TIOCLINUX, &twelve) < 0) {
        console = "/dev/console";

        if (ioctl(0, TIOCGSERIAL, &si) == -1)
            console = NULL;
    }
    else
        console = "/dev/ttyS0";

    if (console && !weird) {
        fd = open(console, O_RDWR, 0);
        if (fd < 0)
            console = "/dev/tts/0";

        if (fd < 0) {
            logMessage(ERROR, "failed to open %s", console);
            return -1;
        }
    }

    return fd;
}

static void set_term(int fd, GHashTable *cmdline) {
    if (!strcmp(ttyname(fd), "/dev/hvc0")) {
        /* using an HMC on a POWER system, use vt320 */
        setenv("TERM", "vt320", 1);
    } else {
        if (cmdline && g_hash_table_lookup_extended(cmdline, "utf8", NULL, NULL))
            setenv("TERM", "vt100", 1);
        else
            /* use the no-advanced-video vt100 definition */
            setenv("TERM", "vt100-nav", 1);
    }
}
#endif

void init_serial(struct termios *orig_cmode, int *orig_flags, GHashTable *cmdline) {
#if !defined(__s390__) && !defined(__s390x__)
    int fd;

    /* We need to get the original mode and flags here (in addition to inside
     * get_serial) so we'll have them for later when we restore the console
     * prior to rebooting.
     */
    get_mode_and_flags(orig_cmode, orig_flags);

    if (!serial_requested(cmdline) || (fd = get_serial_fd()) == -1) {
        /* This is not a serial console install. */
        if ((fd = open("/dev/tty1", O_RDWR, 0)) < 0) {
            if ((fd = open("/dev/vc/1", O_RDWR, 0)) < 0) {
                fprintf(stderr, "failed to open /dev/tty1 and /dev/vc/1");
                exit(1);
            }
        }
    }
    else {
        struct winsize winsize;

        if (ioctl(fd, TIOCGWINSZ, &winsize)) {
            logMessage(ERROR, "failed to get window size");
            exit(1);
        }

        winsize.ws_row = 24;
        winsize.ws_col = 80;

        if (ioctl(fd, TIOCSWINSZ, &winsize)) {
            logMessage(ERROR, "failed to set window size");
            exit(1);
        }

        set_term(fd, cmdline);
    }

    setsid();
    if (ioctl(0, TIOCSCTTY, NULL))
        fprintf(stderr, "could not set new controlling tty\n");

    if (dup2(fd, 0) == -1)
       logMessage(ERROR, "dup2(%d): %m", __LINE__);

    if (dup2(fd, 1) == -1)
       logMessage(ERROR, "dup2(%d): %m", __LINE__);

    if (dup2(fd, 2) == -1)
       logMessage(ERROR, "dup2(%d): %m", __LINE__);

    if (fd > 2)
        close(fd);
#else
    dup2(0, 1);
    dup2(0, 2);
#endif

    /* disable Ctrl+Z, Ctrl+C, etc ... but not in rescue mode */
    if (cmdline && !g_hash_table_lookup_extended(cmdline, "rescue", NULL, NULL)) {
        struct termios ts;

        tcgetattr(0, &ts);
        ts.c_iflag &= ~BRKINT;
        ts.c_iflag |= IGNBRK;
        ts.c_iflag &= ~ISIG;
        tcsetattr(0, TCSANOW, &ts);
    }
}
