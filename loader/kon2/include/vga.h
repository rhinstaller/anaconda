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

/* vga.h -- definitions used in video drivers */

#ifndef	VGA_H
#define	VGA_H

/* Sequencer */
#define	VGASEQ_ADDR	0x3C4
#define	VGASEQ_DATA	0x3C5
#define	VGASEQ_CNT	5

/* CRT controller */
/*
#define	VGACRT_ADDR	0x3D4
#define	VGACRT_DATA	0x3D5
*/
#define	CGACRT_ADDR	0x3D4
#define	CGACRT_DATA	0x3D5
#define	VGACRT_CNT	25
#define	CGACRT_CNT	25

/* Graphics controller */
#define	VGAGRP_ADDR	0x3CE
#define	VGAGRP_DATA	0x3CF
#define	VGAGRP_CNT	9

/* Attribute controller */
#define	VGAATTR_A_O	0x3C0
#define	VGAATTR_DATA	0x3C1
#define	VGAATTR_CNT	21
#define	EGAATTR_CNT	20

#if defined(linux)
#define GRAPH_BASE 0xA0000
#elif defined(__FreeBSD__)
#define GRAPH_BASE 0x0
#endif
#define FONT_SIZE  0x2000

#define	VGA_FONT_SIZE	128
#define	VGA_FONT_HEIGHT	16

#define	NUM_VIDEOH_INFO	4
#define	NUM_VIDEOV_INFO	4

/* DAC Palette */
#define	VGAPAL_OADR	0x3C8
#define	VGAPAL_IADR	0x3C7
#define	VGAPAL_DATA	0x3C9

/* Misc */
#define	VGAMISC_IN	0x3CC
#define	VGAMISC_OUT	0x3C2

/* Input Stat 1 */
/*#define	VGAST1_ADDR	0x3DA*/

#define	MAX_PELS	16

struct vgaRegs {
	u_char	crt[VGACRT_CNT],
		att[VGAATTR_CNT],
		gra[VGAGRP_CNT],
		seq[VGASEQ_CNT],
		mis;
};

struct pelRegs {
	u_char	red[MAX_PELS],
		grn[MAX_PELS],
		blu[MAX_PELS];
};

union videoTimings {
    struct {
	int hDot, hStart, hEnd, hTotal;
	int vLine, vStart, vEnd, vTotal;
	int txmax, tymax, i;
    } m;
    int v[NUM_VIDEOH_INFO+NUM_VIDEOV_INFO+1];
};

static inline
    void	VgaOutByte(u_char value)
{
    __asm__	("movb %%al, %%ah\n\t"
		 "movb $8, %%al\n\t"
		 "outw %%ax, %w1"
		 :/* no outputs */
		 :"a" ((u_char) value),
		 "d" ((u_short)VGAGRP_ADDR));
}

extern u_int vgaCrtAddr, vgaCrtData, vgaSt1Addr;

extern int LineComp9, LineComp8, gramHead;
extern struct vgaRegs regText, regGraph;
extern struct videoInfo SvgaInfo;

void VgaSetRegisters(struct vgaRegs *regs);
void VgaInit(void);
void VgaTextMode(void);
void VgaGraphMode(void);
void VgaWput(u_char *code, u_char fc, u_char bc);
void VgaSput(u_char *code, u_char fc, u_char bc);
void VgaWputFm(u_char *code, u_char fc, u_char bc);
void VgaSputFm(u_char *code, u_char fc, u_char bc);
void VgaHardScrollUp(int line);
void VgaHardScrollDown(int line);
void VgaSetCursorAddress(struct cursorInfo *ci, u_int x, u_int y);
void VgaSetAddress(u_int p);
void VgaCursor(struct cursorInfo *ci);
void VgaClearAll(void);
void VgaScreenSaver(bool blank);
int VgaReadPels(const char *str);
int VgaReadNewRegs(const char *str, union videoTimings *);
int VgaAttach(void);
void VgaDetach(void);
void VgaDefaultCaps();
void VgaLoadRomFont(char *);
#endif
