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

#include	<config.h>

#include	<stdio.h>
#include	<stdlib.h>
#include	<string.h>
#include	<unistd.h>
#include        <errno.h>

#include	<getcap.h>

#include	<defs.h>
#include	<version.h>
#include	<vc.h>

static char *startupStr, *execProg;

int	ConfigExecProg(const char *string)
{
	execProg = strdup(string);
	return SUCCESS;
}

#ifndef	MINI_KON

static int	ConfigStartup(const char *string)
{
	startupStr = strdup(string);
	return SUCCESS;
}

static void	RunStartupCmd(void)
{
	char *p;

	p = strtok(startupStr, "\n");
	while(p) {
		system(p);
		p = strtok(NULL, "\n");
	}
}

static bool startupMessage;

static int	ConfigMessage(const char *confstr)
{
	startupMessage = BoolConf(confstr);
	return SUCCESS;
}

void	ChildInit(void)
{
	DefineCap("StartupMessage", ConfigMessage, "On");
	DefineCap("StartUp", ConfigStartup, NULL);
}

#endif

void	ChildCleanup(void)
{
	free(startupStr);
}

void	ChildStart(FILE *errfp)
{
	char	*tail, *tcap;
	char	buff[256];
	extern char *TermName();

#ifndef	MINI_KON
	char	*shell;
	setgid(getgid());
	setuid(getuid());

	RunStartupCmd();
#endif

#if defined(linux)
#ifdef	MINI_KON
	strcpy(buff, "TERM=linux");
#else
	strcpy(buff, "TERM=kon");
#endif
#elif defined(__FreeBSD__)
	sprintf(buff,"TERM=vt100");
#endif

	tcap = strdup(buff);
	putenv(tcap);

#ifndef	MINI_KON
	if (startupMessage)
	    printf("\rKON2 Kanji On Console " VERSION
		   " using VT number %c\r\n"
		   "%*s\r\n"
		   "%*s\r\n", *(TermName()+8),
		   dInfo.txmax,
		   "Copyright (C) "
		   "1993-1996  Takashi MANABE",
		   dInfo.txmax,
		   "1993, 1994 MAEDA Atusi   ");
#if defined(__FreeBSD__)
	printf("\rKON for FreeBSD-2.x ver0.01 Takashi OGURA\r\n");
#endif

	fflush(stdout);
#endif

	if (execProg)
	    execlp(execProg, execProg, 0);
	else {
	    if ((execProg = getenv("SHELL")) == NULL)
		execProg = "/bin/sh";
	    if ((tail = rindex(execProg, '/')) == NULL)
		tail = " sh";
	    sprintf(buff, "-%s", tail + 1);
	    execl(execProg, buff, 0);
	}
	fprintf(errfp, "KON> couldn't exec shell\r\n");
	fprintf(errfp, "%s: %s\r\n", execProg, strerror(errno));
	exit(EXIT_FAILURE);
}
