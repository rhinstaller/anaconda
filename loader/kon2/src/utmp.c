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

/*
	Original utmp.c was ported from Wnn by komeda@ics.osaka-u.ac.jp.
	This code is written by manabe@papilio.tutics.tut.ac.jp,
	and this does not contain old code (Wnn's setutmp.c).

	Thanks to komeda@ics.osaka-u.ac.jp.
*/

#include <config.h>

#ifndef	MINI_KON

#include	<stdio.h>
#include	<unistd.h>
#include	<fcntl.h>
#include	<string.h>
#include	<pwd.h>
#include	<utmp.h>
#include	<grp.h>
#include	<sys/stat.h>

static int ttyGid;

void	SetUtmp(char *tty)
{
#ifdef linux
	struct utmp	utmp;
	struct passwd	*pw;
	struct group	*ttygrp;
	char	*tn;

	pw = getpwuid(getuid());
	tn = rindex(tty, '/') + 1;
	memset((char *)&utmp, 0, sizeof(utmp));
	strncpy(utmp.ut_id, tn + 3, sizeof(utmp.ut_id));
	utmp.ut_type = DEAD_PROCESS;
	setutent();
	getutid(&utmp);
	utmp.ut_type = USER_PROCESS;
	utmp.ut_pid = getpid();
	strncpy(utmp.ut_line, tn, sizeof(utmp.ut_line));
	strncpy(utmp.ut_user, pw->pw_name, sizeof(utmp.ut_user));
	time(&(utmp.ut_time));
	pututline(&utmp);
	endutent();
	if ((ttygrp = getgrnam("tty")) != NULL)
		ttyGid = ttygrp->gr_gid;
	else
		ttyGid = -1;
	chmod(tty, 0622);
	chown(tty, getuid(), ttyGid);
#endif
}

void	ResetUtmp(char *tty)
{
#ifdef linux
	struct utmp	utmp, *utp;
	char	*tn;

	tn = rindex(tty, '/') + 4;
	memset((char *)&utmp, 0, sizeof(utmp));
	strncpy(utmp.ut_id, tn, sizeof(utmp.ut_id));
	utmp.ut_type = USER_PROCESS;
	setutent();
	utp = getutid(&utmp);
	utp->ut_type = DEAD_PROCESS;
	memset(utp->ut_user, 0, sizeof(utmp.ut_user));
	utp->ut_type = DEAD_PROCESS;
	time(&(utp->ut_time));
	pututline(utp);
	endutent();
	chmod(tty, 0600);
	chown(tty, 0, ttyGid);
#endif
}
#endif	/* MINI_KON */
