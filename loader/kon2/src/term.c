/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992-1996 Takashi MANABE (manabe@papilio.tutics.tut.ac.jp)
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY TAKASHI MANABE ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE TERRENCE R. LAMBERT BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 * 
 */

#include	<stdio.h>
#include	<stdlib.h>
#include	<unistd.h>
#include	<string.h>
#include	<termios.h>
#if defined(__FreeBSD__)
#include	<machine/console.h>
#endif
#include	<signal.h>
#include	<errno.h>
#if defined(linux)
#include	<sys/vt.h>
#include	<sys/kd.h>
#endif
#include	<sys/time.h>
#include	<sys/ioctl.h>
#include	<sys/file.h>
#include	<sys/wait.h>

#include	<config.h>
#include	<getcap.h>

#include	<defs.h>
#include	<errors.h>
#ifndef	MINI_KON
#include	<setutmp.h>
#endif
#include	<version.h>
#include	<vc.h>
#include	<vt.h>
#include	<child.h>
#include	<interface.h>
#include	<sock.h>
#ifdef	MINI_KON
static int mouseFd=-1;
#else
static int sockFd;
#include	<mouse.h>
#endif

#ifdef __FreeBSD__
#define TCSETA     TIOCSETA
#define TCGETA     TIOCGETA
#define SIGCLD     SIGCHLD
#define XCASE 0
#endif

int	masterPty;			 /* master pseudo-tty file descriptor */

#define	MAX_TTYNAME	10

static int	childPid, slavePty;
static struct termios	oldTio;
static char	ptyName[MAX_TTYNAME + 1];
static int orgVtNum = -1;

struct initInfo {
    bool display;			 /* display initialized */
    bool utmp;			 /* utmp set */
    bool socket;			 /* socket opened */
    bool termios;			 /* termios saved */
};

static struct initInfo init;

static void	CleanUp(void)
{
    if (init.display && con.active) {
	TextMode();
    }
#ifndef	MINI_KON
    if (init.utmp)
	ResetUtmp(ptyName);
    if (init.socket)
	SocketKill(sockFd);
#endif
    if (init.termios)
	tcsetattr(0, TCSAFLUSH, &oldTio);
    signal(SIGCHLD, SIG_DFL);
    signal(SIGHUP, SIG_DFL);
    signal(SIGTERM, SIG_DFL);
    signal(SIGSEGV, SIG_DFL);
    signal(SIGUSR1, SIG_DFL);
    signal(SIGUSR2, SIG_DFL);
#ifndef	MINI_KON
    FontDetach(TRUE);
#endif
}

static void	ExitTerm(int signum)
{
    fatal(sys_siglist[signum]);
}

static void	ExitPty(int signum)
{
    int	stat;

#if defined(__FreeBSD__)
    signal(SIGCLD, SIG_DFL);
#endif
    if (wait3(&stat, WNOHANG, 0) != childPid) {
	TextMode();
	kill(0, SIGTSTP);
	GraphMode();
	kill(childPid, SIGCONT);
	signal(SIGCLD, ExitPty);
	return;
    }
    if (WEXITSTATUS(stat) & 0x7f)
	if (WIFSIGNALED(stat))
	    fatal("child died with signal -- %s\r\n", sys_siglist[WTERMSIG(stat)]);
	else
	    fatal("child exited with status %d\r\n", WEXITSTATUS(stat) & 0x7f);
    else if (signum == SIGHUP) {
	fprintf(stderr, "\r\nKON> switched to new VC\r\n");
	exit(EXIT_SUCCESS);
    } else {
	fprintf(stderr, "\r\nKON> finished\r\n");
	exit(EXIT_SUCCESS);
    }
}

static fd_set orgReadFds;
static int numFds;

#ifndef	MINI_KON
void MouseSetRfd(int mfd)
{
    if (mfd > 0) FD_SET(mfd, &orgReadFds);
    if (mfd > sockFd) numFds = mfd + 1;
    else numFds = sockFd + 1;
}

void MouseResetRfd(int mfd)
{
    if (mfd > 0) FD_CLR(mfd, &orgReadFds);
    numFds = sockFd + 1;
}
#endif

static void	ConsoleHandler(void)
{
    static u_char	buff[BUFSIZ + 1];
    fd_set readFds;
    int	i = 0;
    struct timeval tv;

    FD_ZERO(&orgReadFds);
    FD_SET(0, &orgReadFds);
    FD_SET(masterPty, &orgReadFds);
#ifdef	MINI_KON
    numFds = masterPty + 1;
#else
    FD_SET(sockFd, &orgReadFds);
    if (mInfo.has_mouse && mouseFd > 0)
	MouseSetRfd(mouseFd);
    else
	MouseResetRfd(mouseFd);
#endif
    /* Note: we use timeout on select call even if cursor blink is off
       because of screen saver and mouse cursor timeout. */
    while (1) {
	int	v;
	
	do {
	    /* Idle loop. */
	    PollCursor(FALSE);
	    readFds = orgReadFds;
	    tv.tv_sec = 0;
	    tv.tv_usec = 100000; /* 0.1 sec */
	    v = select(numFds, &readFds, NULL, NULL, &tv);
	} while (v == 0 || (v < 0 && (errno == EINTR || mouseFd < 0)));
	if (v < 0) {
	    PerrorExit("select");
	}
	if (FD_ISSET(masterPty, &readFds)) {
	    i = read(masterPty, buff, BUFSIZ);
	    if (i > 0) {
		if (con.text_mode) {
		    write(1, buff, i);
		} else {
/*		    buff[i] = 0;*/
		    VtEmu(buff, i);
		    TextRefresh();
		}
	    }
	}
	if (FD_ISSET(0, &readFds)) {
	    i = read(0, buff, BUFSIZ);
#ifdef	MINI_KON
	    if (i == 3 && !strncmp("\x1b\x5b\x50", buff, 3)) {
		VgaChangeClock();
	    } else
#endif
	    if (i > 0) write(masterPty, buff, i);
#if	0
	    {
		FILE *fff;
		fff = fopen("in.log", "a");
		fwrite(buff, i, 1, fff);
		fclose(fff);
	    }
#endif
	    PollCursor(TRUE);
	}
#ifndef	MINI_KON
	if (FD_ISSET(sockFd, &readFds)) SocketInterface(sockFd);
	if (mInfo.has_mouse) {
	    if (FD_ISSET(mouseFd, &readFds) && con.active) {
		i = read(mouseFd, buff, BUFSIZ);
		if (i > 0) MouseGetPacket(buff, i);
		PollCursor(TRUE);
	    }
	}
#endif
    }
}

static void	ProcessArgs(int argc, const char *argv[])
{
    int	i = 0;
    const	char *video = "NORMAL";
    extern int ConfigExecProg(const char *);
    
    if (argc > 0 && argv[0][0] != '-') {
	video = argv[0];
	i++;
    }
    ConsoleInit(video);
    while (i < argc) {
	const char	*arg;

	if (argv[i][0] != '-') {
	    warn("bad arg `%s'; assumed `-%s'\r\n", argv[i]);
	    arg = (char *) argv[i];
	} else
	    arg = (char *) argv[i] + 1;
	i++;
	if (i >= argc) {
	    error("no value for `%s'\r\n", arg);
	    break;
	}
	if (!strcasecmp(arg, "e"))
	    ConfigExecProg(argv[i]);
	else if (SetCapArg(arg, argv[i]) < 0)
	    warn("invalid capability `%s' ignored\r\n", arg);
	i++;
    }
}

static int	savedArgc;		 /* argc of startup time */
static const char	**savedArgv;	 /* argv of startup time */

/* Do initialization before reading config file */
void	TermInit(int argc, const char *argv[])
{
    int	i;
    
    init.display = init.utmp = init.socket = init.termios = FALSE;
    /* Initialize subsystems. */
    
    CapInit();

#ifndef	MINI_KON
    ChildInit();
    MouseInit();
#endif

    VtInit();
    ProcessArgs(argc, argv);
    savedArgc = argc;
    savedArgv = malloc(argc * sizeof(const char *));
    for (i = 0; i < argc; i++) {
	savedArgv[i] = strdup(argv[i]);
    }
}

static int	TryTermReset(int argc, const char *argv[])
{
    int	i;
    
    fprintf(stderr, "KON> resetting kon for args [");
    for (i = 0; i < argc; i++) {
	fprintf(stderr, " %s", argv[i]);
    }
    fprintf(stderr, " ]...\r\n");
    CapInit();
    ConsoleCleanup();
#ifndef	MINI_KON
    if (mInfo.has_mouse)
	MouseCleanup();
    MouseInit();
#endif
#if 0
    VtCleanup();
#endif
    init.display = FALSE;
    VtInit();
    ProcessArgs(argc, argv);
    return ReadConfig(CONFIG_NAME);
}

/* Called from SocketInterface with stream fd. */
void	TermRestart(int fd)
{
    int	i;
    int	argc;
    char	**argv;
    
    read(fd, &argc, sizeof(argc));
    argv = alloca(argc * sizeof(char *));
    for (i = 0; i < argc; i++) {
	int	len;
	
	read(fd, &len, sizeof(len));
	argv[i] = alloca(len + 1); /* +1 for '\0' */
	read(fd, argv[i], (size_t) len);
	argv[i][len] = '\0';
    }
    TextMode();
    if (TryTermReset(argc, (const char **)argv) < 0 &&
	TryTermReset(savedArgc, savedArgv) < 0 &&
	TryTermReset(0, (const char **)NULL) < 0)
	fatal("giving up\r\n");
#ifndef	MINI_KON
    if (mInfo.has_mouse)
	mouseFd = MouseStart();
#endif
    VtStart();
    ConsoleStart();
    init.display = TRUE;
    message("reset done\r\n");
}

char *
TermName()
{
    static char *tty;

    if (!tty) {
	char *tmp;

	tmp = ttyname(0);
	tty = strdup(strcmp(tmp, "/dev/console") ? tmp: "/dev/tty1");
    }
    return(tty);
}

/* Start processing */
void	TermStart(void)
{
    struct termios	newTio;
    char	ls, ln;
#ifdef	MINI_KON
    extern void LoadMiniFont();
#endif
    
    /* Open PTY(master) */
    for (ls = 'p'; ls <= 's'; ls ++) {
	for (ln = 0; ln <= 0xF; ln ++) {
	    sprintf(ptyName, "/dev/pty%1c%1x", ls, ln);
	    if ((masterPty = open(ptyName, O_RDWR)) >= 0) break;
	}
	if (masterPty >= 0) break;
    }
    if (masterPty < 0) {
	message("can not get master pty\r\n");
	PerrorExit(ptyName);
    }
    ptyName[5] = 't';

#ifndef	MINI_KON
    if (mInfo.has_mouse) {
	mouseFd = MouseStart();
    }
#endif

#ifndef	MINI_KON
    chown("/dev/tty0", getuid(), getgid());
#if defined(linux)
    sockFd = SocketInit(TermName() + 8);
#elif defined(__FreeBSD__)
    sockFd = SocketInit(ttyname(0) + 9);
#endif
#endif
    init.socket = TRUE;

    /* Get old tio of 0 */
    tcgetattr(0, &oldTio);
    init.termios = TRUE;
    
#ifndef	MINI_KON
    SetUtmp(ptyName);
#endif
    init.utmp = TRUE;

    /* fork handler */
    if ((childPid = fork()) < 0) {
	PerrorExit("fork");
    }
    if (childPid != 0) {
	/* I'm parent. */
	atexit(CleanUp);
	ChildCleanup();

#ifdef	MINI_KON
	LoadMiniFont();
#endif
	/* Signal Setting */
	signal(SIGCHLD, ExitPty);
	signal(SIGHUP, ExitTerm);
	signal(SIGTERM, ExitTerm);
	signal(SIGSEGV, ExitTerm);
	/* Set new tio of 0 */
	newTio = oldTio;
	newTio.c_lflag &= ~(ECHO|ISIG|ICANON|XCASE);
	newTio.c_iflag = 0;
	newTio.c_oflag &= ~OPOST;
	newTio.c_cc[VMIN] = 1;
	newTio.c_cc[VTIME] = 0;
#if defined(__FreeBSD__)
	newTio.c_cc[VDISCARD] = _POSIX_VDISABLE;
	newTio.c_cc[VLNEXT] = _POSIX_VDISABLE;
	newTio.c_cc[VSTART] = _POSIX_VDISABLE;
      	newTio.c_cc[VSTOP] = _POSIX_VDISABLE;
      	newTio.c_cc[VINTR] = _POSIX_VDISABLE;
	newTio.c_cc[VSUSP] = _POSIX_VDISABLE;
	newTio.c_cc[VDSUSP] = _POSIX_VDISABLE;
	newTio.c_cc[VQUIT] = _POSIX_VDISABLE;
#endif
	newTio.c_cflag |= CS8;
#ifdef linux
	newTio.c_line = 0;
#endif
	tcsetattr(0, TCSAFLUSH, &newTio);
	/* VGA initialize */
	VtStart();
	ConsoleStart();
	init.display = TRUE;
#ifndef	MINI_KON
	FontAttach();
#endif
	ConsoleHandler();
    } else {
	int	efd;
	FILE	*errfp;
	
	efd = dup(2);
	errfp = fdopen(efd, "w");
	/* I'm child */
	/* Make me process leader */
	setsid();
#if defined(__FreeBSD__)
	{
	  int devtty;
	  if ((devtty = open("/dev/tty",O_RDWR|O_NDELAY)) >= 0) {
	    ioctl(devtty, TIOCNOTTY, (char *)0);
	    close(devtty);
	  }
	}
#endif
	/* Open TTY(slave) */
	if ((slavePty = open(ptyName, O_RDWR)) < 0) {
	    PerrorExit(ptyName);
	}
	close(masterPty);
	/* Set old tio to TTY */
	tcsetattr(slavePty, TCSAFLUSH, &oldTio);
#ifdef __FreeBSD__
	ioctl(slavePty, TIOCSCTTY, (char *)0);
#endif
	/* Set std??? to pty */
	dup2(slavePty, 0);
	dup2(slavePty, 1);
	dup2(slavePty, 2);
	ChildStart(errfp);
    }
}

void ChangeOrgConsole()
{
    int cfd;

#if defined(linux)
    cfd = open("/dev/console", O_WRONLY);
    if (cfd < 0 && (cfd = open("/dev/console", O_RDONLY)) < 0) {
      PerrorExit("/dev/console");
    }
#elif defined(__FreeBSD__)
    cfd = open("/dev/vga", O_WRONLY);
    if (cfd < 0 && (cfd = open("/dev/vga", O_RDONLY)) < 0) {
	PerrorExit("/dev/vga");
    }
#endif
    ioctl(cfd, VT_ACTIVATE, orgVtNum);
    close(cfd);
}

void ChangeNewConsole()
{
#if defined(linux)
    struct vt_stat vts;
#endif
    int cfd, vfd, vtNum, child, parent, mode;
    char vtty[MAX_TTYNAME + 1];

#if defined(linux)
    cfd = open("/dev/console", O_WRONLY);
    if (cfd < 0 && (cfd = open("/dev/console", O_RDONLY)) < 0)
	fatal("can't open /dev/console");
#elif defined(__FreeBSD__)
    cfd = open("/dev/vga", O_WRONLY);
    if (cfd < 0 && (cfd = open("/dev/vga", O_RDONLY)) < 0)
	fatal("can't open /dev/vga");
#endif
    ioctl(cfd, KDGETMODE, &mode);
    if (mode == KD_TEXT) {
	close(cfd);
	return;
    }
#if defined(linux)
    ioctl(cfd, VT_GETSTATE, &vts);
    orgVtNum = vts.v_active;
#endif
    ioctl(cfd, VT_OPENQRY, &vtNum);
    if (vtNum < 0)
	fatal("can't get free VC");
    parent = getpid();
    if ((child = fork()) == -1)
	PerrorExit("fork");
    if (child) {
	signal(SIGHUP, ExitPty);
	pause();
    }
    setsid();
#if defined(linux)
    sprintf(vtty, "/dev/tty%d", vtNum);
#elif defined(__FreeBSD__)
    sprintf(vtty, "/dev/ttyv%d", vtNum);
#endif
    if ((vfd = open(vtty, O_RDWR)) < 0)
	fatal("can't open %s", vtty);
    if (ioctl(cfd, VT_ACTIVATE, vtNum) != 0)
	fatal("can't activate VC(%d)", vtNum);
    atexit(ChangeOrgConsole);
    close(cfd);
    dup2(vfd, 0);
    dup2(vfd, 1);
    dup2(vfd, 2);
    kill(parent, SIGHUP);
}
