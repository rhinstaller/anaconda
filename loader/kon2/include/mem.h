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

static inline
    void PortOutw(u_short value, u_short port)
{
    __asm__ ("outw %0,%1"
	     ::"a" ((u_short) value),
	     "d" ((u_short) port));
}

static inline
    void PortOutb(char value, u_short port)
{
    __asm__ ("outb %0,%1"
	     ::"a" ((char) value),
	     "d" ((u_short) port));
}

static inline
    void lzero(void *head, int n)
{
    __asm__ ("cld\n\t"
	     "rep\n\t"
	     "stosl"
	     ::"a" (0),
	     "c" (n>>2),
	     "D" ((long)head)
	     :"cx","di");
}

static inline
    void bmove(void *dst, void *src, int n)
{
    __asm__ ("cld\n\t"
	     "rep\n\t"
	     "movsb\n\t"
	     ::"c" (n),
	     "D" ((long)dst),
	     "S" ((long)src)
	     :"cx","di","si");
}

static inline
    void brmove(void *dst, void *src, int n)
{
    __asm__ ("std\n\t"
	     "rep\n\t"
	     "movsb\n\t"
	     ::"c" (n),
	     "D" ((long)dst),
	     "S" ((long)src)
	     :"cx","di","si");
}

static inline
    void bzero2(void *head, int n)
{
    __asm__ ("cld\n\t"
	     "rep\n\t"
	     "stosb"
	     ::"a" (0),
	     "c" (n),
	     "D" ((long)head)
	     :"cx","di");
}

extern u_char PortInb(u_short);
extern void wzero(void *, int);
extern void wmove(void *, void *, int);
extern void lmove(void *, void *, int);
extern void SafeFree(void **);

#endif
