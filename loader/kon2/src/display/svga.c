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

#ifdef	MINI_KON
#define	vgaCrtAddr	0x3D4
#define	vgaCrtData	0x3D5
#define	vgaSt1Addr	0x3DA
#endif

static
    void SvgaSetStartAddress(void)
{
    int	til;
    
    til = (dInfo.gydim - 1 - (gramHead / dInfo.glineByte)) << 4;
    
    PortOutw((gramHead  & 0xff00) | 0x0c, vgaCrtAddr);
    PortOutw((gramHead << 8) | 0x0d, vgaCrtAddr);
    PortOutw((til << 4) | 0x18, vgaCrtAddr);
    PortOutw((til & 0x1000) | LineComp8, vgaCrtAddr);
    PortOutw(((til & 0x2000) << 1) | LineComp9, vgaCrtAddr);
}

struct videoInfo SvgaInfo =
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
    SvgaSetStartAddress,
    VgaHardScrollUp,
    VgaHardScrollDown
    };

int SvgaSetVideoType(struct videoInfo *info, const char *regs)
{
    union videoTimings video;

    *info = SvgaInfo;
    VgaReadNewRegs(regs, &video);
    if (VgaAttach() < 0) return FAILURE;
    VgaDefaultCaps();
    return SUCCESS;
}

#endif
