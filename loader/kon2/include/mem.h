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

/* mem -- memory handling libraries */

#ifndef MEM_H
#define MEM_H

static __inline__
    void PortOutw(u_short value, u_short port)
{
    __asm__ volatile ("outw %0,%1"
	     ::"a" ((unsigned short) value), "d"((unsigned short) port));
}

static __inline__
    void PortOutb(char value, u_short port)
{
    __asm__ volatile ("outb %0,%1"
	      ::"a" ((unsigned char) value), "d"((unsigned short) port));
}

static __inline__
    unsigned char PortInb(unsigned short port)
{
    unsigned char value;
    __asm__ volatile ("inb %1,%0"
		      :"=a" (value)
		      :"d"((unsigned short) port));
    return value;
}

extern u_char PortInb(u_short);
extern void wzero(void *, int);
extern void wmove(void *, void *, int);
extern void lmove(void *, void *, int);
extern void SafeFree(void **);

#endif
