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
 * 3. All advertising materials mentioning features or use of this software
 *    must display the following acknowledgement:
 *      This product includes software developed by Terrence R. Lambert.
 * 4. The name Terrence R. Lambert may not be used to endorse or promote
 *    products derived from this software without specific prior written
 *    permission.
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

#ifndef	MINI_KON

#include	<stdio.h>
#include	<stdlib.h>
#include	<unistd.h>
#include	<string.h>
#include	<sys/types.h>
#include	<sys/time.h>
#include	<sys/file.h>
#include	<sys/types.h>
#include	<sys/socket.h>

#include	<defs.h>
#include	<errors.h>
#include	<interface.h>
#include	<sock.h>
#include	<fnld.h>
#include	<vc.h>
#include	<vt.h>
#include	<term.h>

void StatReport()
{
    int i;

    i = 0;
    while (fSRegs[i].registry) {
	message("%2X %-15s %c%c\r\n",
		i, fSRegs[i].registry,
		(i == lInfo.sb) ? '*':' ',
		(fSRegs[i].stat & FR_ATTACH) ? 'A':
		((fSRegs[i].stat & FR_PROXY) ? 'P':' '));
	i ++;
    }
    i = 0;
    while (fDRegs[i].registry) {
	message("%2X %-15s %c%c\r\n",
		i|CHR_DBC, fDRegs[i].registry,
		(i == lInfo.db) ?
		((lInfo.sc == CODE_EUC) ? 'E':
		((lInfo.sc == CODE_SJIS) ? 'S':' ')): ' ',
		(fDRegs[i].stat & FR_ATTACH) ? 'A':
		((fDRegs[i].stat & FR_PROXY) ? 'P':' '));
	i ++;
    }
}

int	SocketInit(char *tty)
{
    int	len, sfd;
    struct	sockaddr sinfo;

#if defined(linux)
    sprintf(sinfo.sa_data, "/tmp/.kon%s", tty);
#elif defined(__FreeBSD__)
    sprintf(sinfo.sa_data, "/tmp/.kon");
#endif
    unlink(sinfo.sa_data);
    if ((sfd = socket(AF_UNIX, SOCK_STREAM, 0)) < 0) {
	PerrorExit(sinfo.sa_data);
    }
    sinfo.sa_family = AF_UNIX;
    len = sizeof(sinfo.sa_family) + strlen(sinfo.sa_data) + 1;
    if (bind(sfd, &sinfo, len) < 0) {
	message("can't bind socket");
	PerrorExit(sinfo.sa_data);
    }
    listen(sfd, 1);
    chown(sinfo.sa_data, getuid(), getgid());
    return(sfd);
}

void	SocketInterface(int sfd)
{
    int	fd, len;
    struct	sockaddr clt;
    struct messageHeader mh;

    len = sizeof(struct sockaddr);
    if ((fd = accept(sfd, &clt, &len)) < 0) PerrorExit("accept");
    SocketRecCommand(fd, &mh);
    switch(mh.cmd) {
    case CHR_LOAD:
	FontAttach();
	break;
    case CHR_UNLOAD:
	FontDetach(FALSE);
	break;
    case CHR_TEXTMODE:
	TextMode();
	message("switched to text mode.\r\n");
	SocketSendCommand(fd, CHR_ACK);
	break;
    case CHR_GRAPHMODE:
	GraphMode();
	message("switched to graphics mode.\r\n");
	SocketSendCommand(fd, CHR_ACK);
	break;
    case CHR_RESTART:
	SocketSendCommand(fd, CHR_ACK);
	TermRestart(fd);
	break;
    case CHR_STAT:
	SocketSendCommand(fd, CHR_ACK);
	StatReport();
	break;
    default:
	message("unknown request.\r\n");
	SocketSendCommand(fd, CHR_NAK);
    }
    close(fd);
}
#endif
