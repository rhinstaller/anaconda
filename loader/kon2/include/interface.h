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

/* interface.h -- communication protocol definition */

#ifndef	INTERFACE_H
#define	INTERFACE_H

#include	<sys/types.h>

/* 通信制御キャラクタ */
#define	STR_NAK		"\x15"
#define	CHR_NAK		0x15
#define	STR_ACK		"\x06"
#define	CHR_ACK		0x06

/* 通信内容の識別子 */
#define	CHR_SFONT	0x81
#define	CHR_WFONT	0x89

#define	CHR_SFLD	0x80
#define	CHR_DBC		0x20
#define	CHR_DFLD	(CHR_SFLD|CHR_DBC)

#define	CHR_LOAD	'L'
#define	CHR_UNLOAD	'U'
#define	CHR_STAT	'S'
#define	CHR_DISCONNECT	'D'
#define	CHR_TEXTMODE	'T'
#define	CHR_GRAPHMODE	'G'
#define	CHR_RESTART	'R'

#define	MAX_SOCKET_NAME	14
#define	SOCKET_BASENAME	"/tmp/.kon"

#define	SHMEM_NAME	CONFIG_NAME

/* 制御キャラクタの最大長 */
#define	MAX_CTRLCHAR	80

/*
extern char	socketName[MAX_SOCKET_NAME+1];
*/

struct	messageHeader	{
	u_char	cno,	/* client number */
		cmd;	/* command */
};

struct	fontInfo {
    u_int size;
    u_char high, width, type;
};

struct fontLoaderRegs {
    u_int (*addr)(u_char ch1, u_char ch2);
    u_int max;
};

extern struct fontLoaderRegs fldSRegs[], fldDRegs[];

extern void	SocketKill(int);
extern int	SocketRecCommand(int, struct messageHeader *);
extern int	SocketSendCommand(int, char);
extern int	SocketClientOpen(void);
extern int	SocketSendData(u_char *buff, int size, int fd);
extern int	CheckLoadedFont(char type);
extern int	SetFont(char *prog, u_char *font, struct fontInfo *fi);

#endif
