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

#include	<config.h>

#ifndef	MINI_KON

#ifdef	HAS_VGA

#include	<stdio.h>
#include	<fcntl.h>
#include	<termios.h>
#include	<string.h>
#include	<unistd.h>
#include	<sys/mman.h>
#include	<linux/mm.h>
#include	<sys/kd.h>
#undef free
#include	<stdlib.h>

#include	<mem.h>
#include	<getcap.h>
#include	<defs.h>
#include	<errors.h>
#include	<vc.h>
#include	<vt.h>
#include	<vga.h>
#include	<fnld.h>

#define R5x_MASK	0x7737

union s3Regs {
    struct {
	u_char r3[10];/* Video Atribute (CR30-34, CR38-3C) */
	u_char rx[33];/* Video Atribute (CR40-65) */
    } x;
    struct {
	u_char
	    x30, x31, x32, x33, x34,
	    x38, x39, x3a, x3b, x3c;
	u_char
	    x40, x41, x42, x43, x44, x45, x46, x47,
	    x48, x49, x4a, x4b, x4c, x4d, x4e, x4f,
	    x50, x51, x53, x54, x55, x58, x59, x5a, x5c, x5d, x5e,
	    x60, x61, x62, x63, x64, x65;
    } r;
} s3Text, s3Graph;

static
    void S3SetRegisters(union s3Regs *regs)
{
    int i, n;

    PortOutw(0xa539, vgaCrtAddr); /* unlock system control regs */
    for (i = 0; i < 5; i ++) {
	PortOutb(0x30 + i, vgaCrtAddr);
	PortOutb(regs->x.r3[i], vgaCrtData);
	PortOutb(0x38 + i, vgaCrtAddr);
	PortOutb(regs->x.r3[5+i], vgaCrtData);
    }
    for (i = 0; i < 16; i ++) {
	PortOutb(0x40 + i, vgaCrtAddr);
	PortOutb(regs->x.rx[i], vgaCrtData);
    }
    for (n = 16, i = 0; i < 16; i ++) {
	if ((1 << i) & R5x_MASK) {
	    PortOutb(0x50 + i, vgaCrtAddr);
	    PortOutb(regs->x.rx[n], vgaCrtData);
	    n ++;
	}
    }
    for (i = 0; i < 6; i ++, n ++) {
	PortOutb(0x60 + i, vgaCrtAddr);
	PortOutb(s3Text.x.rx[n], vgaCrtData);
    }
}

static
    void S3SetStartAddress(void)
{
    u_int til;

    PortOutb(0x31, vgaCrtAddr);
    PortOutb(((gramHead & 0x030000) >> 12) | s3Graph.r.x31, vgaCrtData);
    s3Graph.r.x51 &= ~0x03;
    s3Graph.r.x51 |= ((gramHead & 0x040000) >> 18);
    PortOutb(0x51, vgaCrtAddr);
    /* Don't override current bank selection */
    PortOutb((PortInb(vgaCrtData) & ~0x03)
	     | ((gramHead & 0x40000) >> 18), vgaCrtData);

    PortOutw((gramHead & 0xFF00) | 0x0c, vgaCrtAddr);
    PortOutw(((gramHead & 0x00FF) << 8) | 0x0d, vgaCrtAddr);
    
    til = dInfo.gydim - 1 - (gramHead / dInfo.glineByte);
    PortOutw((til << 8) | 0x18, vgaCrtAddr);
    PortOutw(((til & 0x100) << 4) | LineComp8, vgaCrtAddr);
    PortOutw(((til & 0x200) << 5) | LineComp9, vgaCrtAddr);
    PortOutw(0x8d31, vgaCrtAddr); /* unlock system control regs */
}

static
    void S3TextMode(void)
{
    VgaTextMode();
    S3SetRegisters(&s3Text);
}

static
    void S3CalcNewRegs(union videoTimings *video)
{
    regGraph.mis |= 0x0D;
/*    regGraph.crt[19] = 0xA0;*/
/*    regGraph.crt[20] = 0xA0;*/
    regGraph.crt[23] = 0xE3;
/*    regGraph.crt[24] = 0;*/
    s3Graph.r.x5e = (((video->m.vTotal - 2) & 0x400) >> 10)
	| (((video->m.vLine - 1) & 0x400) >> 9)
	    | ((video->m.vStart & 0x400) >> 8)
		| ((video->m.vStart & 0x400) >> 6) | 0x40;
    s3Graph.r.x5d = ((video->m.hTotal & 0x800) >> 11)
	| ((video->m.hDot & 0x800) >> 10)
	    | ((video->m.hStart & 0x800) >> 9)
		| ((video->m.hStart & 0x800) >> 7);
}

static
    void S3GraphMode(void)
{
/*    s3Graph.r.x35 = s3Text.r.x35 & 0xF0;*/
#if 1
    s3Graph.r.x5c = 0x20;
    s3Graph.r.x31 = 0x8D;
    s3Graph.r.x32 = 0;
    s3Graph.r.x33 = 0x20;
    s3Graph.r.x34 = 0x10;
/*    s3Graph.r.x35 = 0;*/
/*    s3Graph.r.x3a = 0x95;*/
    s3Graph.r.x3b = (regGraph.crt[0] + regGraph.crt[4] + 1) / 2;
    s3Graph.r.x3c = regGraph.crt[0] / 2;
    s3Graph.r.x40 = (s3Text.r.x40 & 0xF6) | 1;
    s3Graph.r.x43 = s3Text.r.x44 = 0;
    s3Graph.r.x45 = s3Text.r.x45 & 1;

    s3Graph.r.x50 = s3Text.r.x50 & ~0xC1;
    s3Graph.r.x51 = (s3Text.r.x51 & 0xC0) | ((dInfo.gxdim >> 7) & 0x30);
    s3Graph.r.x53 = s3Text.r.x53 & ~0x30;
    s3Graph.r.x54 = 0xA0;
    s3Graph.r.x55 = (s3Text.r.x55 & 8) | 0x40;
    s3Graph.r.x58 = 0;
    s3Graph.r.x5d |= s3Graph.r.x5d & ~0x17;
    s3Graph.r.x60 = 0x3F;
    s3Graph.r.x61 = 0x81;
    s3Graph.r.x62 = 0;
    if (dInfo.gxdim < 800) {
	s3Graph.r.x50 |= 0x40;
	s3Graph.r.x42 = 0xb;
    } else if (dInfo.gxdim < 1024) {
	s3Graph.r.x50 |= 0x80;
	s3Graph.r.x42 = 2;
    } else {
	s3Graph.r.x42 = 0xE;
    }
    VgaGraphMode();
#endif
    S3SetRegisters(&s3Graph);
}

static
    void S3Init()
{
    int i, n;

    PortOutw(0xa539, vgaCrtAddr); /* unlock system control regs */
/*    PortOutw(0x483b, vgaCrtAddr); /* unlock system control regs */
    for (i = 0; i < 5; i ++) {
	PortOutb(0x30 + i, vgaCrtAddr);
	s3Text.x.r3[i] = PortInb(vgaCrtData);
	PortOutb(0x38 + i, vgaCrtAddr);
	s3Text.x.r3[i+5] = PortInb(vgaCrtData);
    }
    for (i = 0; i < 16; i ++) {
	PortOutb(0x40 + i, vgaCrtAddr);
	s3Text.x.rx[i] = PortInb(vgaCrtData);
    }
    for (n = 16, i = 0; i < 16; i ++) {
	if ((1 << i) & R5x_MASK) {
	    PortOutb(0x50 + i, vgaCrtAddr);
	    s3Text.x.rx[n] = PortInb(vgaCrtData);
	    n ++;
	}
    }
    for (i = 0; i < 6; i ++, n ++) {
	PortOutb(0x60 + i, vgaCrtAddr);
	s3Text.x.rx[n] = PortInb(vgaCrtData);
    }
    s3Graph = s3Text;
    s3Graph.r.x39 = 0xA5;
    VgaInit();
}

static struct videoInfo S3Info =
{
    TRUE,
    S3Init,
    S3TextMode,
    S3GraphMode,
    VgaWput,
    VgaSput,
    VgaSetCursorAddress,
    VgaSetAddress,
    VgaCursor,
    VgaClearAll,
    VgaScreenSaver,
    VgaDetach,
    S3SetStartAddress,
    VgaHardScrollUp,
    VgaHardScrollDown
    };

int S3SetVideoType(struct videoInfo *info, const char *regs)
{
    union videoTimings video;

    *info = S3Info;
    VgaReadNewRegs(regs, &video);
    S3CalcNewRegs(&video);
    if (VgaAttach() < 0) return FAILURE;
    VgaDefaultCaps();
    return SUCCESS;
}

#endif
#endif
