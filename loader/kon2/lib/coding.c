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

#include	<config.h>

#include	<stdio.h>
#include	<errno.h>
#include	<string.h>

#include	<interface.h>
#include	<fnld.h>

static u_int JISX0208(u_char ch1, u_char ch2)
{
    if (ch1 > 0x2A)
	return((ch2 - 0x41 + (ch1 - 0x26) * 96) << 5);
    else
	return((ch2 - 0x21 + (ch1 - 0x21) * 96) << 5);
}

#ifdef	MINI_KON

#define	GB2312	NULL
#define	BIG5	NULL
#define	KSC5601	NULL

#else

static u_int GB2312(u_char ch1, u_char ch2)
{
    if (ch1 > 0x29)
	return(((ch1 - 0x27) * 94 + ch2 - 0x21) << 5);
    else
	return(((ch1 - 0x21) * 94 + ch2 - 0x21) << 5);
}

static u_int BIG5(u_char ch1, u_char ch2)
{
    if (ch2 < 0xA1)
	return(((ch1 - 0xA1) * 157 + ch2 - 0x40) << 5);
    else
	return(((ch1 - 0xA1) * 157 + 63 + ch2 - 0xA1) << 5);
}

static u_int KSC5601(u_char ch1, u_char ch2)
{
    if (ch1 > 0x2D)
	return((ch2 - 0x21 + (ch1 - 0x24) * 96) << 5);
    else
	return((ch2 - 0x21 + (ch1 - 0x21) * 96) << 5);
}

#endif

static u_int FldJISX0208(u_char ch1, u_char ch2)
{
    return(JISX0208(ch1&0x7F, ch2&0x7F));
}

#ifdef	MINI_KON

#define	FldGB2312	NULL
#define	FldKSC5601	NULL

#else

static u_int FldKSC5601(u_char ch1, u_char ch2)
{
    return(KSC5601(ch1&0x7F, ch2&0x7F));
}

static u_int FldGB2312(u_char ch1, u_char ch2)
{
    return(GB2312(ch1&0x7F, ch2&0x7F));
}

#endif

struct fontRegs fSRegs[] = {
    /* latin1(French, Spanish, ...) */
    {    NULL, 0,      "ISO8859-1", NULL, 0, 0, 'B', 'A', 0},
    /* latin2 */
    {    NULL, 0,      "ISO8859-2", NULL, 0, 0, 'B', 'B', 0},
    /* latin3 */
    {    NULL, 0,      "ISO8859-3", NULL, 0, 0, 'B', 'C', 0},
    /* latin4 */
    {    NULL, 0,      "ISO8859-4", NULL, 0, 0, 'B', 'D', 0},
    /* Russian */
    {    NULL, 0,      "ISO8859-5", NULL, 0, 0, 'B', 'L', 0},
    /* Arabic */
    {    NULL, 0,      "ISO8859-6", NULL, 0, 0, 'B', 'G', 0},
    /* Greek */
    {    NULL, 0,      "ISO8859-7", NULL, 0, 0, 'B', 'F', 0},
    /* Hebrew */
    {    NULL, 0,      "ISO8859-8", NULL, 0, 0, 'B', 'H', 0},
    /* latin5 */
    {    NULL, 0,      "ISO8859-9", NULL, 0, 0, 'B', 'M', 0},
    /* Japanese */
    {    NULL, 0,"JISX0201.1976-0", NULL, 0, 0, 'J', 'I', 0},
    {    NULL, 0,             NULL, NULL, 0, 0,   0,   0, 0}
};

struct fontLoaderRegs fldSRegs[] = {
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,   0xFF},
    {       NULL,      0},
};

struct fontRegs fDRegs[] = {
    /* DF_GB2312 */
    {  GB2312, 0,  "GB2312.1980-0", NULL, 0, 0, 'A', 0, 0},
    /* DF_JISX0208 */
    {JISX0208, 0,"JISX0208.1983-0", NULL, 0, 0, 'B', 0, 0},
    /* DF_KSC5601 */
    { KSC5601, 0, "KSC5601.1987-0", NULL, 0, 0, 'C', 0, 0},
    /* DF_JISX0212 */
    {JISX0208, 0,       "JISX0212", NULL, 0, 0, 'D', 0, 0},
    /* DF_BIG5_0 */
    {    BIG5, 0,     "BIG5.HKU-0", NULL, 0, 0, '0', 0, 0},
    /* DF_BIG5_1 */
    {    BIG5, 0,     "BIG5.HKU-0", NULL, 0, 0, '1', 0, 0},
    {    NULL, 0,             NULL, NULL, 0, 0,   0, 0, 0}
};

struct fontLoaderRegs fldDRegs[] = {
    {  FldGB2312,      0},
    {FldJISX0208, 0x7424},
    { FldKSC5601, 0x7D7E},
    {FldJISX0208, 0x7424},
    {       BIG5,      0},
    {       BIG5,      0},
    {       NULL,      0}
};

int CodingByRegistry(char *reg)
{
    int i;

    i = 0;
    while (fSRegs[i].registry) {
	if (!strncasecmp(fSRegs[i].registry, reg, strlen(reg)))
	    return(i|CHR_SFLD);
	i ++;
    }
    i = 0;
    while (fDRegs[i].registry) {
	if (!strncasecmp(fDRegs[i].registry, reg, strlen(reg)))
	    return(i|CHR_DFLD);
	i ++;
    }
    return(-1);
}
