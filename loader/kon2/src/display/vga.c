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

#ifdef	HAS_VGA

#include	<stdio.h>
#include	<fcntl.h>
#include	<termios.h>
#include	<string.h>
#include	<unistd.h>
#include	<sys/mman.h>
#if defined(linux)
/* #include	<linux/mm.h> */
#include	<sys/kd.h>
#elif defined(__FreeBSD__)
#include      <vm/vm_param.h>
#include      <sys/ioctl.h>
#include      <machine/console.h>
vm_size_t page_size;
#endif
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

static struct pelRegs grapPels, textPels;

struct vgaRegs
    regText,
    regGraph = {
	{	/* CRT */
	    0x5F,0x4F,0x50,0x82,0x54,0x80,0x0B,0x3E,
	    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
	    0xEA,0x0C,0xDF,0x28,0x00,0xE7,0x04,0xE3,
	    0xFF
	}, {	/* ATT */
	    0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
	    0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
	    0x01,0x00,0x0F,0x00,0x00
	}, {	/* GRA */
	    0x00,0x0F,0x00,0x20,0x03,0x00,0x05,0x00,
	    0xFF
	}, {	/*SEQ */
	    0x03,0x01,0x0F,0x00,0x06
	}, /* MIS */
	    0xE3
    };

int LineComp9, LineComp8, gramHead;
#ifdef	MINI_KON
#define	vgaCrtAddr	0x3D4
#define	vgaCrtData	0x3D5
#define	vgaSt1Addr	0x3DA
#else
u_int vgaCrtAddr = 0x3D4;
u_int vgaCrtData = 0x3D5;
u_int vgaSt1Addr = 0x3DA;
#endif

static	char	*gramMem;		/* dummy buffer for mmapping grahics memory */
static	char	*fontBuff1;		/* saved font data - plane 2 */

static	bool	savePlane3;
static	char	*fontBuff2;		/* saved font data - plane 3 */

static	u_int	writeAddr;		 /* address to write next character */

static	bool	kanjiCursor;
static	u_char	cursorTop, cursorBtm;

#ifndef	MINI_KON
static	u_short	fmPattern;		 /* bit pattern to modify font; skip line if bit clear */
#endif

void VgaSetRegisters(struct vgaRegs *regs)
{
    int	i;
    
    /* disable video */
    PortInb(vgaSt1Addr);	
    PortOutb(0x00, VGAATTR_A_O);
    
    /* update misc output register */
    PortOutb((regs->mis&~0x1)|(PortInb(VGAMISC_IN)&0x01), VGAMISC_OUT);
    
    /* synchronous reset on */
    PortOutb(0x00,VGASEQ_ADDR);
    PortOutb(0x01,VGASEQ_DATA);	
    
    /* write sequencer registers */
    for (i = 1; i < VGASEQ_CNT; i++) {
	PortOutb(i, VGASEQ_ADDR);
	PortOutb(regs->seq[i], VGASEQ_DATA);
    }
    
    /* synchronous reset off */
    PortOutb(0x00, VGASEQ_ADDR);
    PortOutb(0x03, VGASEQ_DATA);
    
    /* deprotect CRT registers 0-7 */
    PortOutb(0x11, vgaCrtAddr);
    PortOutb(PortInb(vgaCrtData)&0x7F, vgaCrtData);
    
    /* write CRT registers */
    for (i = 0; i < VGACRT_CNT; i++) {
	PortOutb(i, vgaCrtAddr);
	PortOutb(regs->crt[i], vgaCrtData);
    }
    
    /* write graphics controller registers */
    for (i = 0; i < VGAGRP_CNT; i++) {
	PortOutb(i, VGAGRP_ADDR);
	PortOutb(regs->gra[i], VGAGRP_DATA);
    }
    
    /* write attribute controller registers */
    for (i = 0; i < VGAATTR_CNT; i++) {
	/* reset flip-flop */
	PortInb(vgaSt1Addr);
	PortOutb(i, VGAATTR_A_O);
	PortOutb(regs->att[i],VGAATTR_A_O);
    }
}

static
void VgaSetPELS(struct pelRegs *pels)
{
    int i;
    
    for(i = 0; i < MAX_PELS; i++) {
	PortOutb(i, VGAPAL_OADR);
	PortOutb(pels->red[i], VGAPAL_DATA);
	PortOutb(pels->grn[i], VGAPAL_DATA);
	PortOutb(pels->blu[i], VGAPAL_DATA);
    }
}

static
void VgaGetPELS(struct pelRegs *pels)
{
    int	i;
    
    PortOutb(0, VGAPAL_IADR);
    for(i = 0; i < MAX_PELS; i++) {
	pels->red[i] = PortInb(VGAPAL_DATA);
	pels->grn[i] = PortInb(VGAPAL_DATA);
	pels->blu[i] = PortInb(VGAPAL_DATA);
    }
}

static inline
void	VgaSetColor(u_char col)
{
    static	old;
    
    if (old == col) return;
    PortOutw(col << 8, VGAGRP_ADDR);
    old = col;
}

void VgaInit(void)
{
    int	i;

    VgaGetPELS(&textPels);
    
    /* disable video */
    PortInb(vgaSt1Addr);	
    PortOutb(0x00, VGAATTR_A_O);
    /* save text mode VGA registers */
    for (i = 0; i < VGACRT_CNT; i++) {
	PortOutb(i, vgaCrtAddr);
	regText.crt[i] = PortInb(vgaCrtData);
    }
    for (i = 0; i < VGAATTR_CNT; i++) {
	PortInb(vgaSt1Addr);
	PortOutb(i, VGAATTR_A_O);
	regText.att[i] = PortInb(VGAATTR_DATA);
    }
    for (i = 0; i < VGAGRP_CNT; i++) {
	PortOutb(i, VGAGRP_ADDR);
	regText.gra[i] = PortInb(VGAGRP_DATA);
    }
    for (i = 0; i < VGASEQ_CNT; i++) {
	PortOutb(i, VGASEQ_ADDR);
	regText.seq[i] = PortInb(VGASEQ_DATA);
    }
    regText.mis = PortInb(VGAMISC_IN);
    
    PortOutb(PortInb(VGAMISC_IN)|0x01, VGAMISC_OUT);
    VgaSetRegisters(&regGraph);
    
    /* save font data in plane 2 */
    PortOutw(0x0204, VGAGRP_ADDR);
    memcpy(fontBuff1, gramMem, FONT_SIZE);
#ifdef	USE_ROMFONT
    VgaLoadRomFont(fontBuff1);
#endif
#if defined(MINI_KON) || defined(USE_STATICFONT)
    VgaLoadStaticFont();
#endif

    if (savePlane3 && fontBuff2) {
	/* save font data in plane 3 */
	PortOutw(0x0304, VGAGRP_ADDR);
	memcpy(fontBuff2, gramMem, FONT_SIZE);
    }
}

void VgaTextMode(void)
{
    /* disable video */
    PortInb(vgaSt1Addr);
    PortOutb(0x00, VGAATTR_A_O);

    /* restore font data - first select a 16 color graphics mode */
    VgaSetRegisters(&regGraph);

    /* disable Set/Reset Register */
    PortOutb(0x01, VGAGRP_ADDR );
    PortOutb(0x00, VGAGRP_DATA );
    
    /* restore font data in plane 2 - necessary for all VGA's */
    PortOutb(0x02, VGASEQ_ADDR );
    PortOutb(0x04, VGASEQ_DATA );
    memcpy(gramMem, fontBuff1, FONT_SIZE);
    
    if (savePlane3) {
	/* restore font data in plane 3 - necessary for Trident VGA's */
	PortOutb(0x02, VGASEQ_ADDR );
	PortOutb(0x08, VGASEQ_DATA );
	memcpy(gramMem, fontBuff2, FONT_SIZE);
    }
    
    /* restore text mode VGA registers */
    VgaSetRegisters(&regText);
    
    /* set text palette */
    
    VgaSetPELS(&textPels);
    
    /* enable video */
    PortInb(vgaSt1Addr);
    PortOutb(0x20, VGAATTR_A_O);
}

void VgaGraphMode(void)
{
    /* disable video */
    PortInb(vgaSt1Addr); 		
    PortOutb(0x00, VGAATTR_A_O);	
    
    VgaSetRegisters(&regGraph);

    /* set default palette */
    
    VgaSetPELS(&grapPels);
    
    /* enable video */
    PortInb(vgaSt1Addr);
    PortOutb(0x20, VGAATTR_A_O);
}

#ifdef	MINI_KON
void VgaChangeClock()
{
    static int clock=-1;

    if (clock < 0) clock = (regGraph.mis >> 2) & 3;
    clock = (clock + 1) & 3;
    regGraph.mis &= ~(3 << 2);
    regGraph.mis |= clock << 2;
printf("%d\r\n", clock);
    VgaGraphMode();
}    
#endif

void VgaWput(u_char *code, u_char fc, u_char bc)
{
    volatile char	*gram, *vcls;
    u_char *til;
    u_char	x;
    
    VgaSetColor(bc&7);
    vcls = gram = gramMem + writeAddr;
    for (x = 0;x < dInfo.glineChar;x ++, vcls += dInfo.glineByte)
	*vcls = *(vcls + 1) = 0;
    VgaSetColor(fc);
    if (bc & 0x8) {
	vcls -= dInfo.glineByte;
	*vcls = *(vcls + 1) = 0;
    }
    til = code + (dbFReg->high << 1);
    for (;code < til; code ++, gram += dInfo.glineByte) {
	if (*code) {
	    VgaOutByte(*code);
	    *gram = *gram;
	}
	code ++;
	if (*code) {
	    VgaOutByte(*code);
	    *(gram + 1) = *(gram + 1);
	}
    }
    VgaOutByte(0xFF);
}

void VgaSput(u_char *code, u_char fc, u_char bc)
{
    volatile char *gram, *vcls;
    u_char *til;
    u_char	x;

    vcls = gram = gramMem + writeAddr;
    VgaSetColor(bc&7);
    for (x = 0;x < dInfo.glineChar;x ++, vcls += dInfo.glineByte)
	*vcls = 0;
    if (!code) return;
    VgaSetColor(fc);
    if (bc & 0x8) *(vcls - dInfo.glineByte) = 0;
    til = code + sbFReg->high;
    for (;code < til;code ++, gram += dInfo.glineByte) {
	if (*code) {
	    VgaOutByte(*code);
	    *gram = *gram;
	}
    }
    VgaOutByte(0xFF);
}

#ifndef	MINI_KON

void VgaWputFm(u_char *code, u_char fc, u_char bc)
{
    volatile char	*gram, *vcls;
    u_char	x;
    u_short	fm = (1 << (dbFReg->high - 1));
    
    VgaSetColor(bc&7);
    vcls = gram = gramMem + writeAddr;
    for (x = 0;x < dInfo.glineChar;x ++, vcls += dInfo.glineByte)
	*vcls = *(vcls + 1) = 0;
    VgaSetColor(fc);
    if (bc & 0x8) {
	vcls -= dInfo.glineByte;
	*vcls = *(vcls + 1) = 0;
    }
    for (x = 0;x < dbFReg->high;x ++, code ++, fm >>= 1) {
	if (*code) {
	    VgaOutByte(*code);
	    *gram = *gram;
	}
	code ++;
	if (*code) {
	    VgaOutByte(*code);
	    *(gram + 1) = *(gram + 1);
	}
	if (fm & fmPattern)
	    gram += dInfo.glineByte;
    }
    VgaOutByte(0xFF);
}

void VgaSputFm(u_char *code, u_char fc, u_char bc)
{
    volatile char	*gram, *vcls;
    u_char	x;
    u_short	fm = (1 << (sbFReg->high - 1));
    
    vcls = gram = gramMem + writeAddr;
    VgaSetColor(bc&7);
    for (x = 0;x < dInfo.glineChar;x ++, vcls += dInfo.glineByte)
	*vcls = 0;
/*    if (!code) return;*/
    VgaSetColor(fc);
    if (bc & 0x8) *(vcls - dInfo.glineByte) = 0;
    if (code) for (x = 0;x < sbFReg->high;x ++, code ++, fm >>= 1) {
	if (*code) {
	    VgaOutByte(*code);
	    *gram = *gram;
	}
	if (fm & fmPattern)
	    gram += dInfo.glineByte;
    }
    VgaOutByte(0xFF);
}
#endif

void VgaHardScrollUp(int line)
{
    int	oldhead;
    
    VgaSetColor((con.attr & ATTR_REVERSE ? con.fcol:con.bcol)&7);
    
    if (line > dInfo.tymax) {
	line %= dInfo.tymax + 1;
	bzero(gramMem, dInfo.gsize);
    }
    
    oldhead = gramHead;
    gramHead += line * dInfo.tlineByte;
    if (gramHead >= dInfo.gsize) {
	gramHead -= dInfo.gsize;
	bzero(gramMem + oldhead, dInfo.gsize - oldhead);
/*	if (gramHead) bzero(gramMem, gramHead);*/
	bzero(gramMem, gramHead);
    } else bzero(gramMem + oldhead, gramHead - oldhead);
    vInfo.set_start_address();
}

void VgaHardScrollDown(int line)
{
    int	oldhead;
    
    VgaSetColor((con.attr & ATTR_REVERSE ? con.fcol:con.bcol)&7);
    
    if (line > dInfo.tymax) {
	line %= dInfo.tymax + 1;
	bzero(gramMem, dInfo.gsize);
    }
    
    oldhead = gramHead;
    gramHead -= line * dInfo.tlineByte;
    if (gramHead < 0) {
	gramHead += dInfo.gsize;
/*	if (oldhead) bzero(gramMem, oldhead);*/
	bzero(gramMem, oldhead);
	bzero(gramMem + gramHead, dInfo.gsize - gramHead);
    } else bzero(gramMem + gramHead, oldhead - gramHead);
    vInfo.set_start_address();
}

void VgaSetCursorAddress(struct cursorInfo *ci, u_int x, u_int y)
{
#if 0
    if (x > dInfo.txmax) {
	y ++;
	x -= dInfo.txmax + 1;
    }
#endif
    ci->addr = (y * dInfo.tlineByte + cursorTop
		* dInfo.glineByte + x + gramHead) % dInfo.gsize;
}

void VgaSetAddress(u_int p)
{
    writeAddr = (p%dInfo.glineByte) + (p/dInfo.glineByte) * dInfo.tlineByte;
}

void VgaCursor(struct cursorInfo *ci)
{
    volatile char	*gram;
    u_char	x;
    int	bottom = cursorBtm + 1 <= dInfo.glineChar ?
	cursorBtm + 1 : dInfo.glineChar;
    
    VgaSetColor(15);
    gram = gramMem + ci->addr;
    
    PortOutw(0x0F00, VGAGRP_ADDR);	/* color white */
    PortOutw(0x1803, VGAGRP_ADDR);	/* XOR mode */
    x = cursorTop;
    if (kanjiCursor && ci->kanji) {
	for (;x < bottom;x ++, gram += dInfo.glineByte) {
	    *gram = *gram;
	    *(gram + 1)= *(gram + 1);
	}
    } else
	for (;x < bottom;x ++, gram += dInfo.glineByte)
	    *gram = *gram;
    PortOutw(0x0003, VGAGRP_ADDR);	/* unmodify mode */
}

void VgaClearAll(void)
{
    VgaSetColor((con.attr & ATTR_REVERSE ? con.fcol:con.bcol)&7);
    bzero(gramMem, dInfo.gsize);
}

void VgaScreenSaver(bool blank)
{
    if (blank) {
	PortOutb(0x01, VGASEQ_ADDR);
	PortOutb(PortInb(VGASEQ_DATA) | 0x20, VGASEQ_DATA);
    } else {
	PortOutb(0x01, VGASEQ_ADDR);
	PortOutb(PortInb(VGASEQ_DATA) & 0xDF, VGASEQ_DATA);
    }
}

int VgaReadPels(const char *str)
{
    int	i, red, grn, blu;
    
    for (i = 0; i < MAX_PELS; i ++) {
	sscanf(str, "%d %d %d", &red, &grn, &blu);
	if ((str = strchr(str, '\n')) == NULL) {
	    error("PELS entry too short\r\n");
	    return FAILURE;
	}
	str++;			/* skip '\n' */
	grapPels.red[i] = red;
	grapPels.grn[i] = grn;
	grapPels.blu[i] = blu;
    }
    return SUCCESS;
}	

int VgaReadNewRegs(const char *str, union videoTimings *video)
{
    int	i, clock, txmax, tymax;
    char *line2;

    for (i = 0; i < NUM_VIDEOH_INFO+NUM_VIDEOV_INFO; i ++) {
        if (! *str) {
	    error("%d values required for vga registers, "
		  "but only supplied %d\r\n", VGACRT_CNT, i);
	    return FAILURE;
	}
	video->v[i] = strtoul(str, (char **) &str, 10);
    }
    line2 = strpbrk(str, "\r\n");
    *line2 = '\0';line2 ++;
    if (*str) video->m.i = atoi(str);
    if (sscanf(line2, "%x \n %d %d", &clock, &txmax, &tymax) == EOF) {
	error("missing arg for vga driver\r\n");
	return FAILURE;
    }
    dInfo.gxdim = video->m.hDot;
    dInfo.gydim = video->m.vLine;
    dInfo.txmax = txmax;
    dInfo.tymax = tymax;
    dInfo.glineChar = dInfo.gydim / (dInfo.tymax + 1);
    dInfo.glineByte = dInfo.gxdim >> 3;
    dInfo.gydim = dInfo.glineChar * (dInfo.tymax + 1);
    dInfo.gsize = dInfo.glineByte * dInfo.gydim;
/*printf("%ld\r\n", dInfo.gsize);*/
    dInfo.tlineByte = dInfo.glineChar * dInfo.glineByte;

    if (video->m.vLine < 480) {
	regGraph.crt[23] = 0xE3;
	regGraph.mis = 0xE3;
    } else {
	if (video->m.vLine < 768) regGraph.mis = 0xE3;
	else regGraph.mis = 0x23;
	regGraph.crt[23] = 0xC3;
    }
    regGraph.mis |= (clock & 3) << 2;
    regGraph.crt[0] = (video->m.hTotal>>3) - 5;
    regGraph.crt[1] = (video->m.hDot>>3) - 1;
    regGraph.crt[2] = (video->m.hStart>>3) - 1;
    regGraph.crt[3] = ((video->m.hEnd>>3) & 0x1F) | 0x80;
    regGraph.crt[4] = video->m.hStart>>3;
    regGraph.crt[5] = (((video->m.hEnd>>3) & 0x20) << 2)
	| ((video->m.hEnd>>3) & 0x1F);
    regGraph.crt[6] = (video->m.vTotal - 2) & 0xFF;
    regGraph.crt[7] = 0x10;
    regGraph.crt[7] |= (((dInfo.gydim - 1) & 0x100) >> 7)
	| (((dInfo.gydim - 1) & 0x200) >> 3);
    regGraph.crt[7] |= ((video->m.vStart & 0x100) >> 6)
	| ((video->m.vStart & 0x100) >> 5);
    regGraph.crt[7] |= (((video->m.vTotal - 2) & 0x100) >> 8)
	| (((video->m.vTotal - 2) & 0x200) >> 4);
    regGraph.crt[7] |= ((video->m.vStart & 0x200) >> 2);
    regGraph.crt[9] = ((video->m.vStart & 0x200) >>4) | 0x40;
    regGraph.crt[16] = video->m.vStart & 0xFF;
    regGraph.crt[17] = (video->m.vEnd & 0x0F) | 0x20;
    regGraph.crt[18] = (dInfo.gydim - 1) & 0xFF;
    regGraph.crt[19] = video->m.hDot >> 4;
    regGraph.crt[21] = video->m.vStart & 0xFF;
    regGraph.crt[22] = (video->m.vStart + 1) & 0xFF;

    LineComp8 = ((regGraph.crt[7] & 0xEF) << 8) + 0x07;
    LineComp9 = ((regGraph.crt[9] & 0xBF) << 8) + 0x09;

    return SUCCESS;
}

/* VGA initialize & uninitialize */

int VgaAttach(void)
{
    int	devMem;

#if defined(linux)
    ioperm(VGAMISC_IN, 1, 1);
#ifndef	MINI_KON
    if (!(PortInb(VGAMISC_IN)&0x01)) { /* monochrome VGA */
	vgaCrtAddr = 0x3B4;
	vgaCrtData = 0x3B5;
	vgaSt1Addr = 0x3BA;
    }
#endif
    
    /* get I/O permissions for VGA registers */
    ioperm(vgaCrtAddr, 1, 1);
    ioperm(VGAATTR_A_O, 1, 1);
    ioperm(VGAGRP_ADDR, 1, 1);
    ioperm(VGASEQ_ADDR, 1, 1);
    ioperm(VGAPAL_OADR, 1, 1);
    ioperm(VGAPAL_IADR, 1, 1);
    ioperm(vgaCrtData, 1, 1);
    ioperm(VGAATTR_DATA, 1, 1);
    ioperm(VGAGRP_DATA, 1, 1);
    ioperm(VGASEQ_DATA, 1, 1);
    ioperm(VGAMISC_IN, 1, 1);
    ioperm(VGAMISC_OUT, 1, 1);
    ioperm(vgaSt1Addr, 1, 1);
    ioperm(VGAPAL_DATA, 1, 1);

    if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
	Perror("/dev/mem");
	return FAILURE;
    }
#elif defined(__FreeBSD__)
    if (ioctl(0, KDENABIO,0) < 0) {
	Perror("ioctl CONSOLE_IO_ENABLE");
	return FAILURE;
    }
    if (ioctl(0, KDSETMODE,KD_GRAPHICS) < 0) {
	Perror("ioctl CONSOLE_IO_ENABLE");
	return FAILURE;
    }
    if ((devMem = open("/dev/vga", O_RDWR|O_NDELAY) ) < 0) {
	Perror("/dev/mem");
	return FAILURE;
    }
#endif
    if ((fontBuff1 = malloc(FONT_SIZE)) == NULL
	|| (savePlane3 && (fontBuff2 = malloc(FONT_SIZE)) == NULL)
	) {
	Perror("malloc ");
	return FAILURE;
    }
    gramMem = (unsigned char *)mmap(
#if defined(linux)
				    (__ptr_t)0,
#else
				    0,
#endif
				    dInfo.gsize,
				    PROT_READ|PROT_WRITE,
#if 0
				    MAP_SHARED|MAP_FIXED,
#else
#if defined(linux)
				    MAP_SHARED,
#elif defined(__FreeBSD__)
				    MAP_FILE|MAP_SHARED,
#endif
#endif
				    devMem,
				    GRAPH_BASE
				    );
    close(devMem);
    if ((long)gramMem < 0) {
	Perror("mmap");
	return FAILURE;
    }
    
    return SUCCESS;
}

void VgaDetach(void)
{
    gramHead = 0;
#if defined(linux)
    ioperm(vgaCrtAddr, 1, 0);
    ioperm(VGAATTR_A_O, 1, 0);
    ioperm(VGAGRP_ADDR, 1, 0);
    ioperm(VGASEQ_ADDR, 1, 0);
    ioperm(VGAPAL_OADR, 1, 0);
    ioperm(VGAPAL_IADR, 1, 0);
    ioperm(vgaCrtData, 1, 0);
    ioperm(VGAATTR_DATA, 1, 0);
    ioperm(VGAGRP_DATA, 1, 0);
    ioperm(VGASEQ_DATA, 1, 0);
    ioperm(VGAMISC_IN, 1, 0);
    ioperm(VGAMISC_OUT, 1, 0);
    ioperm(vgaSt1Addr, 1, 0);
    ioperm(VGAPAL_DATA, 1, 0);
#endif

    munmap(gramMem, dInfo.gsize);
    
    SafeFree((void **)&gramMem);
    SafeFree((void **)&fontBuff1);
    if (savePlane3 && fontBuff2)
	SafeFree((void **)&fontBuff2);
}

/* Configure */

static
    int ConfigPlane3(const char *confstr)
{
    savePlane3 = BoolConf(confstr);
    return SUCCESS;
}

static
    int ConfigKanjiCursor(const char *confstr)
{
    kanjiCursor = BoolConf(confstr);
    return SUCCESS;
}

static
    int ConfigCursorTop(const char *confstr)
{
    cursorTop = atoi(confstr);
    return SUCCESS;
}

static
    int ConfigCursorBottom(const char *confstr)
{
    cursorBtm = atoi(confstr);
    return SUCCESS;
}

void VgaDefaultCaps()
{
    DefineCap("Pels", VgaReadPels, NULL);
    DefineCap("SavePlane3", ConfigPlane3, "Off");
    DefineCap("KanjiCursor", ConfigKanjiCursor, "On");
    DefineCap("CursorTop", ConfigCursorTop, "14");
    DefineCap("CursorBottom", ConfigCursorBottom, "15");
}

#ifndef	MINI_KON

int VgaFmSetVideoType(struct videoInfo *info, const char *regs)
{
    union videoTimings video;

    *info = SvgaInfo;
    info->sput = VgaSputFm;
    info->wput = VgaWputFm;
    fmPattern = (u_short) strtoul(regs, (char **) &regs, 16);
    if (VgaReadNewRegs(regs, &video) == FAILURE) return FAILURE;
    if (VgaAttach() < 0) return FAILURE;
    VgaDefaultCaps();
    return SUCCESS;
}
#endif

#endif
