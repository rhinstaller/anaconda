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
	This code is based on selection.
*/

#include	<config.h>

#ifndef	MINI_KON

#include	<unistd.h>
#include <sys/types.h>
#include	<defs.h>
#include	<mouse.h>

struct mouseInfo	mInfo;

int	mouseFd = -1;

#ifdef	HAS_MOUSE

#include	<stdio.h>
#include	<stdlib.h>
#include	<termios.h>
#include	<fcntl.h>
#include	<string.h>
#include	<getcap.h>

#include	<errors.h>
#include	<vc.h>

static int cFlag;
static int headMask;
static int headId;
static int dataMask;
static int pkMax;

typedef enum {
	MOUSE_MICROSOFT,
	MOUSE_MOUSESYSTEMS,
	MOUSE_BUSMOUSE,
	MOUSE_MMSERIES,
	MOUSE_LOGITECH,
	MOUSE_PS2,
	MOUSE_NONE
} mtype;

static mtype mouseType = MOUSE_NONE;

#define MAX_PK_SIZE	5

struct mouseconf {
	const char *name;
	mtype type;
	int cFlag;
	int headMask;
	int headId;
	int dataMask;
	int pkMax;
} mice[] = {
	{
		"Microsoft", MOUSE_MICROSOFT,
		(CS7|CREAD|CLOCAL|HUPCL),
		0x40, 0x40, 0x40, 3
		},
	{
		"MouseSystems", MOUSE_MOUSESYSTEMS,
		(CS8|CSTOPB|CREAD|CLOCAL|HUPCL),
		0xf8, 0x80, 0x00, 5
		},
	{
		"BusMouse", MOUSE_BUSMOUSE,
		0,
		0xf8, 0x80, 0x00, 5
		},
	{
		"MmSeries", MOUSE_MMSERIES,
		(CS8|PARENB|PARODD|CREAD|CLOCAL|HUPCL),
		0xe0, 0x80, 0x80, 3
		},
	{
		"Logitech", MOUSE_LOGITECH,
		(CS8|CSTOPB|CREAD|CLOCAL|HUPCL),
		0xe0, 0x80, 0x80, 3
		},
	{
		"PS2", MOUSE_PS2,
		(CS8|CREAD|CLOCAL|HUPCL),
		0xcc, 0x08, 0x00, 3
		},
	{
		"None", MOUSE_NONE,
		0,
		0, 0, 0, 0
		},
	{
		NULL, MOUSE_NONE,
		0,
		0, 0, 0, 0
		}
};

static int mouseBaud;

static int	ConfigMouseBaud(const char *config)
{
	int baud;

	sscanf(config, "%d", &baud);

	switch (baud) {
	case 9600:
		mouseBaud = B9600;
		break;
	case 4800:
		mouseBaud = B4800;
		break;
	case 2400:
		mouseBaud = B2400;
		break;
	default:
		kon_warn("invalid mouse baud rate %d; set to default (1200)\r\n", baud);
	case 1200:
		mouseBaud = B1200;
		break;
	}
	return SUCCESS;
}

static char *mouseDev;

static int	ConfigMouseDev(const char *config)
{
	char name[MAX_COLS];
	sscanf(config, "%s", name);

	if (mouseDev) free(mouseDev);
	mouseDev = strdup(name);
	return SUCCESS;
}

static int	pasteButton;

static int      Config3Buttons(const char *config)
{ 
	pasteButton = BoolConf(config) ? MOUSE_MID: MOUSE_RGT;
	return SUCCESS;   
}

static int	ConfigMouse(const char *config)
{
	struct mouseconf *p;
	char name[MAX_COLS];

	mouseType = MOUSE_NONE;
	mInfo.has_mouse = FALSE;
	sscanf(config, "%s", name);
	for (p = mice; p->name != NULL; p++) {
		if (strcasecmp(name, p->name) == 0) {
			mouseType = p->type;
			if (mouseType == MOUSE_NONE)
				return SUCCESS;
			message("mouse type `%s'\r\n", name);
			mInfo.has_mouse = TRUE;
			cFlag     = p->cFlag;
			headMask  = p->headMask;
			headId    = p->headId;
			dataMask  = p->dataMask;
			pkMax     = p->pkMax;

			if (mouseType != MOUSE_BUSMOUSE) {
				DefineCap("MouseBaud", ConfigMouseBaud, "1200");
			}
			DefineCap("Mouse3Buttons", Config3Buttons, "Off");
			DefineCap("MouseDev", ConfigMouseDev, "/dev/mouse");
			return SUCCESS;
		}
	}
	kon_warn("unknown mouse type `%s' ignored; assuming no mouse\r\n", name);
	return SUCCESS;
}

static
void	MouseSetBaud(int mfd, u_short baud, u_short cflag)
{
	struct termios mio;
	char	*cf;

	tcgetattr(mfd, &mio);

	mio.c_iflag = IGNBRK | IGNPAR;
	mio.c_oflag = 0;
	mio.c_lflag = 0;
#ifdef linux
	mio.c_line = 0;
#endif
	mio.c_cc[VTIME] = 0;
	mio.c_cc[VMIN] = 1;

	mio.c_cflag = cflag;
	cfsetispeed(&mio, baud);
	cfsetospeed(&mio, baud);

	tcsetattr(mfd, TCSAFLUSH, &mio);

	switch(mouseBaud) {
	case B9600:	cf = "*q"; break;
	case B4800:	cf = "*p"; break;
	case B2400:	cf = "*o"; break;
	case B1200:	cf = "*n"; break;
	}

	mio.c_cflag = cflag;
	cfsetispeed(&mio, mouseBaud);
	cfsetospeed(&mio, mouseBaud);
	write(mfd, cf, 2);
	usleep(100000);
	tcsetattr(mfd, TCSAFLUSH, &mio);
}

void	MouseInit(void)
{
	mInfo.has_mouse = TRUE;
	DefineCap("Mouse", ConfigMouse, "NONE");
}

int	MouseStart(void)
{
    int	mfd;
    
    if ((mfd = open(mouseDev, O_RDWR|O_NONBLOCK)) < 0) {
	kon_warn("couldn't open mouse device; mouse disabled\n");
	Perror(mouseDev);
	free(mouseDev);
	mouseDev = NULL;
	mInfo.has_mouse = FALSE;
	return -1;
    }
    
    if (mouseType != MOUSE_BUSMOUSE) {
	MouseSetBaud(mfd, B9600, cFlag);
	MouseSetBaud(mfd, B4800, cFlag);
	MouseSetBaud(mfd, B2400, cFlag);
	MouseSetBaud(mfd, B1200, cFlag);
	
	if (mouseType == MOUSE_LOGITECH) {
	    write(mfd, "S", 1);
	    MouseSetBaud(mfd, mouseBaud, CS8 | PARENB | PARODD | CREAD |
			 CLOCAL | HUPCL);
	}
	
	write(mfd, "Q", 1);
    }
    
    mouseFd = mfd;
    return(mfd);
}

void	MouseCleanup(void)
{
    close(mouseFd);
    mouseFd = -1;
}

static
void	MouseAnalyzePacket(u_char *packet)
{
	static char oldstat;
	static int	dx, dy;

	switch (mouseType) {
	case MOUSE_NONE:
		return;
	case MOUSE_MICROSOFT:
		mInfo.stat = ((packet[0] & 0x20) >> 3) | ((packet[0] & 0x10) >> 4);
		dx += (char)(((packet[0] & 0x03) << 6) | (packet[1] & 0x3F));
		dy += (char)(((packet[0] & 0x0C) << 4) | (packet[2] & 0x3F));
		break;
	case MOUSE_MOUSESYSTEMS:
		mInfo.stat = (~packet[0]) & 0x07;
		dx += (char)(packet[1]) + (char)(packet[3]);
		dy += - ((char)(packet[2]) + (char)(packet[4]));
		break;
	case MOUSE_MMSERIES:
	case MOUSE_LOGITECH:
		mInfo.stat = packet[0] & 0x07;
		dx += (packet[0] & 0x10) ? packet[1]: - packet[1];
		dy += (packet[0] & 0x08) ? - packet[2]: packet[2];
		break;
	case MOUSE_PS2:
		mInfo.stat = ((packet[0] & 0x01) << 2) | ((packet[0] & 0x02) >> 1);
		dx += (char)(packet[1]);
		dy -= (char)(packet[2]);
		break;
	case MOUSE_BUSMOUSE:
		mInfo.stat = (~packet[0]) & 0x07;
		dx += (char)packet[1];
		dy += - (char)packet[2];
		break;
	}
	mInfo.dx = dx >> 3;
	dx -= mInfo.dx << 3;
	mInfo.dy = dy / dInfo.glineChar;
	dy -= mInfo.dy * dInfo.glineChar;

	mInfo.sw = MOUSE_LIFETIME;
	if (mInfo.dx || mInfo.dy) {
		mInfo.x += mInfo.dx;
		mInfo.y += mInfo.dy;

		if (mInfo.x < 0) mInfo.x = 0;
		else if (mInfo.x > dInfo.txmax) mInfo.x = dInfo.txmax;
		if (mInfo.y < 0) mInfo.y = 0;
		else if (mInfo.y > dInfo.tymax) mInfo.y = dInfo.tymax;
	}
	if (mInfo.stat & MOUSE_LFT) {
		if (!(oldstat & MOUSE_LFT)) {
			mInfo.sx = mInfo.x;
			mInfo.sy = mInfo.y;
		} else if (mInfo.dx || mInfo.dy) {
			TextReverse(mInfo.sx, mInfo.sy, mInfo.x, mInfo.y);
			TextRefresh();
			TextReverse(mInfo.sx, mInfo.sy, mInfo.x, mInfo.y);
		}
	} else if (oldstat & MOUSE_LFT)
		TextCopy(mInfo.sx, mInfo.sy, mInfo.x, mInfo.y);

	if (mInfo.stat & pasteButton && !(oldstat & pasteButton)) TextPaste();
	oldstat = mInfo.stat;
}

void	MouseGetPacket(u_char *buff, int size)
{
	static u_char	packet[MAX_PK_SIZE];
	static	stat = 0;
	int	n;

	for (n = 0; n < size; n ++, buff ++) {
		if (!stat) {
			if ((*buff & headMask) == headId) {
				packet[0] = *buff;
				stat = 1;
			}
			continue;
		}
		if (mouseType != MOUSE_PS2
		    && ((*buff & dataMask) || *buff == 0x80)) {
			stat = 0;
			continue;
		}
		packet[stat] = *buff;
		stat ++;
		if (stat == pkMax) {
			MouseAnalyzePacket(packet);
			stat = 0;
		}
	}
}

#else	/* HAS_MOUSE */

/* Dummy routines. */

void	MouseInit(void)
{
	mInfo.has_mouse = FALSE;
}

void	MouseGetPacket(u_char *buff, int size)
{
}

int	MouseStart(void)
{
	return -1;
}

void	MouseCleanup(void)
{
}

#endif
#endif
