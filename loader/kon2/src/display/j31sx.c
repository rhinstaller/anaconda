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
	This code is based on vgalib.

	Thanks to frandsen@diku.dk (Tommy Frandsen).
*/

/*
	This code is modified for DCGA by obuk@MIX.

	Thanks to obuk@MIX.
*/

#include	<config.h>

#ifdef	HAS_J31SX

#include	<stdio.h>
#include	<fcntl.h>
#include	<termios.h>
#include	<string.h>
#include	<unistd.h>
#include	<sys/mman.h>
/* #include	<linux/mm.h> */
#include	<sys/kd.h>
#undef free
#include	<stdlib.h>

#include	<mem.h>
#include	<getcap.h>
#include	<defs.h>
#include	<errors.h>
#include	<vc.h>

#define COLUMNS  80
#define ROWS     25

#define GRAPH_BASE 0xB8000
#define GRAPH_SIZE (LSIZE*NLINES)

#define LSIZE (0x800*4)
#define NLINES 4

#define LINE0 (0*LSIZE)
#define LINE1 (1*LSIZE)
#define LINE2 (2*LSIZE)
#define LINE3 (3*LSIZE)

#define CGA_DATA   0x3d4
#define CGA_MODE   0x3d8
#define CGA_COLOR  0x3d9
#define CGA_STATUS 0x3da

struct cgaRegs {
	u_char mode;
	u_char data[16];
	u_char color;
};

static struct cgaRegs
	regText = {
		0x2d & ~8,                                       /* mode */
	{
		0x71, 0x50, 0x5a, 0x0a, 0x1f, 0x06, 0x19, 0x1c,  /* data */
		0x02, 0x07, 0x06, 0x07, 0x00, 0x00, 0x00, 0x00,
	},
		0x30,                                            /* color */
	},
	regGraph = {
		0x1e & ~8,                                       /* mode */
	{
		0x38, 0x28, 0x2d, 0x0a, 0x7f, 0x06, 0x64, 0x7d,  /* data */
		0x02, 0x03, 0x06, 0x07, 0x00, 0x00, 0x00, 0x00,
	},
		0x3f,                                            /* color */
	};


static	char	*gram;			 /* dummy buffer for mmapping grahics memory */
static	int	origin = 0;
static	int	scroll = 0;
static	int	mode;
static	u_int	writeAddr;		 /* address to write next character */

static	bool	boxCursor;
static	bool	kanjiCursor;

#define DIM(x) (sizeof(x)/sizeof((x)[0]))
#define min(a,b) ((a)<(b)?(a):(b))

static void ClearLines(int top, int bottom);
static void SetOrigin(int pos);
static void DisableVideo(void);
static void EnableVideo(void);
static void SetRegisters(struct cgaRegs *regs);

static u_char wspace[] = {
	0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
	0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
	0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
	0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
};

static inline
void	VgaSetAddress(u_int p)
{
	int row = (p / COLUMNS + scroll) % ROWS;
	int column = p % COLUMNS;
	writeAddr = row*COLUMNS*4 + column;
}


static
void	VgaSput(u_char *code, u_char fc, u_char bc)
{
	int pos, i; char x;
	int underline;

	underline = fc & ATTR_ULINE;
	fc &= 7; bc &= 7;
	if (!code || fc == bc) code = wspace;
	x = (fc < bc)? 0xff: 0x00;

	pos = origin + writeAddr - COLUMNS;
	for (i = 0; i < NLINES; i++) {
		pos = (pos+COLUMNS) & (LSIZE-1);
		gram[pos+LINE0] = x ^ *code++;
		gram[pos+LINE1] = x ^ *code++;
		gram[pos+LINE2] = x ^ *code++;
		gram[pos+LINE3] = x ^ *code++;
	}
	if (underline) {
		gram[pos+LINE3] = 0xff;
	}
}


static
void	VgaWput(u_char *code, u_char fc, u_char bc)
{
	int pos1, pos2, i; char x;
	int underline;

	underline = fc & ATTR_ULINE;
	fc &= 7; bc &= 7;
	if (!code || fc == bc) code = wspace;
	x = (fc < bc)? 0xff: 0x00;

	pos1 = origin + writeAddr - COLUMNS;
	for (i = 0; i < NLINES; i++) {
		pos1 = (pos1+COLUMNS) & (LSIZE-1);
		pos2 = (pos1+1) & (LSIZE-1);
		gram[pos1+LINE0] = x ^ *code++; gram[pos2+LINE0] = x ^ *code++;
		gram[pos1+LINE1] = x ^ *code++; gram[pos2+LINE1] = x ^ *code++;
		gram[pos1+LINE2] = x ^ *code++; gram[pos2+LINE2] = x ^ *code++;
		gram[pos1+LINE3] = x ^ *code++; gram[pos2+LINE3] = x ^ *code++;
	}
	if (underline) {
		gram[pos1+LINE3] = 0xff;        gram[pos2+LINE3] = 0xff;
	}
}


static inline
void	VgaSetCursorAddress(struct cursorInfo *ci, u_int x, u_int y)
{
	ci->addr = y*COLUMNS*4 + x;
}

static inline
void	VgaCursor(struct cursorInfo *ci)
{
	int pos, i;

	pos = origin + ci->addr;
	i = 0;
	if (! boxCursor)
	pos += COLUMNS*3; i += 3;

	for (; i < NLINES; i++) {
		pos &= LSIZE-1;
		gram[pos+LINE0] ^= 0xff;
		gram[pos+LINE1] ^= 0xff;
		gram[pos+LINE2] ^= 0xff;
		gram[pos+LINE3] ^= 0xff;
		if (kanjiCursor && ci->kanji) {
			int pos2 = (pos+1) & (LSIZE-1);
			gram[pos2+LINE0] ^= 0xff;
			gram[pos2+LINE1] ^= 0xff;
			gram[pos2+LINE2] ^= 0xff;
			gram[pos2+LINE3] ^= 0xff;
		}
		pos += COLUMNS;
	}
}



static
void	VgaSetStartAddress(void)
{
	SetOrigin(origin);
}

static
void	VgaHardScrollUp(int line)
{
	if (line > ROWS-1) {
		line %= ROWS;
		ClearLines(0, ROWS-1);
	}
	SetOrigin(origin + line*COLUMNS*4);
	ClearLines(ROWS-line, ROWS-1);
	scroll = (scroll-line+ROWS) % ROWS;
}

static
void	VgaHardScrollDown(int line)
{
	if (line > ROWS-1) {
		line %= ROWS;
		ClearLines(0, ROWS-1);
	}
	SetOrigin(origin - line*COLUMNS*4);
	ClearLines(0, line-1);
	scroll = (scroll+line+ROWS) % ROWS;
}


static void ClearLines(int top, int bottom)
{
	int pos, bytes, n;
	if (top > bottom) return;
	pos = origin + top*COLUMNS*4;
	bytes = (bottom+1-top)*COLUMNS*4;
	while (bytes > 0) {
		pos &= (LSIZE-1);
		n = min(bytes, LSIZE-pos);
		bzero2(&gram[pos+LINE0], n);
		bzero2(&gram[pos+LINE1], n);
		bzero2(&gram[pos+LINE2], n);
		bzero2(&gram[pos+LINE3], n);
		pos += n;
		bytes -= n;
	}
}

static
void	VgaClearAll(void)
{
	ClearLines(0, ROWS-1);
}

static
void	VgaScreenSaver(bool blank)
{
	if (blank) {
		DisableVideo();
	} else {
		EnableVideo();
	}
}


static
void	VgaTextMode(void)
{
	SetRegisters(&regText);
	EnableVideo();
}

static
void	VgaGraphMode(void)
{
	SetRegisters(&regGraph);
	EnableVideo();
}

static
void	VgaInit(void)
{
	SetRegisters(&regGraph); /* enter graphics mode */
	lzero(gram, GRAPH_SIZE);
	EnableVideo();
}


static void DisableVideo(void)
{
	PortOutb(mode &= ~8, CGA_MODE);
}


static void EnableVideo(void)
{
	PortOutb(mode |= 8, CGA_MODE);
}


static void SetOrigin(int pos)
{
	int word_address = (origin = pos & (LSIZE-1)) >> 1;
	int hi = word_address >> 8;
	int lo = word_address & 0x00FF;
#ifdef wordport_magic
	PortOutw(12 | (hi << 8), CGA_DATA);
	PortOutw(13 | (lo << 8), CGA_DATA);
#else
	PortOutb(12, CGA_DATA);
	PortOutb(hi, CGA_DATA+1);
	PortOutb(13, CGA_DATA);
	PortOutb(lo, CGA_DATA+1);
#endif
}


static void SetRegisters(struct cgaRegs *regs)
{
	int i;

	PortOutb(0, CGA_MODE);	/* disable video */
	for (i = 0; i < DIM(regs->data); ++i) {
#ifdef wordport_magic
		PortOutw((regs->data[i] << 8) | i, CGA_DATA);
#else
		PortOutb(i, CGA_DATA);
		PortOutb(regs->data[i], CGA_DATA+1);
#endif
	}
	PortOutb(regs->color, CGA_COLOR);
	PortOutb(mode = regs->mode, CGA_MODE);
}

static void	VgaDetach(void)
{
	origin = scroll = 0;
	ioperm(CGA_MODE, 1, 0);
	ioperm(CGA_DATA, 2, 0);
	ioperm(CGA_COLOR, 1, 0);

	munmap(gram, GRAPH_SIZE);

	SafeFree((void **)&gram);
}

static struct videoInfo J31SXInfo =
{
	TRUE,
	VgaInit,
	VgaTextMode,
	VgaGraphMode,
	VgaWput,
	VgaSput,
	VgaSetCursorAddress,
	VgaSetAddress,
	VgaCursor,
	VgaClearAll,
	VgaScreenSaver,
	VgaDetach,
	VgaSetStartAddress,
	VgaHardScrollUp,
	VgaHardScrollDown
};

static int	ConfigKanjiCursor(const char *confstr)
{
	kanjiCursor = BoolConf(confstr);
	return SUCCESS;
}

static int	ConfigBoxCursor(const char *confstr)
{
	boxCursor = BoolConf(confstr);
	return SUCCESS;
}

int	J31SXSetVideoType(struct videoInfo *info, const char *regs)
{
	int	devMem;

	/* Calculate display info */
	dInfo.gxdim = 640;
	dInfo.gydim = 400;
	dInfo.txmax = COLUMNS-1;
	dInfo.tymax = ROWS-1;

	dInfo.glineChar = dInfo.gydim / (dInfo.tymax + 1);
	dInfo.glineByte = dInfo.gxdim >> 3;
	dInfo.gydim = dInfo.glineChar * (dInfo.tymax + 1);
	dInfo.gsize = dInfo.glineByte * dInfo.gydim;
	dInfo.tlineByte = dInfo.glineChar * dInfo.glineByte;

	/* get I/O permissions for VGA registers */
	ioperm(CGA_MODE, 1, 1);
	ioperm(CGA_DATA, 2, 1);
	ioperm(CGA_COLOR, 1, 1);

	if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
		Perror("/dev/mem");
		return FAILURE;
	}
	gram = (unsigned char *)mmap(
		(__ptr_t)0,
		GRAPH_SIZE,
		PROT_READ|PROT_WRITE,
#if 0
		MAP_SHARED|MAP_FIXED,
#else
		MAP_SHARED,
#endif
		devMem,
		GRAPH_BASE
	);
	close(devMem);
	if ((long)gram < 0) {
		Perror("mmap");
		return FAILURE;
	}

	*info = J31SXInfo;
	DefineCap("KanjiCursor", ConfigKanjiCursor, "On");
	DefineCap("BoxCursor", ConfigBoxCursor, "Off");

	return SUCCESS;
}

#endif
