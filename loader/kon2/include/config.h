
/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992, 1993 MAEDA Atusi (mad@math.keio.ac.jp)
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
	NOTE: This is automatically generated config.
	>>>>>>>>>>>>>> DO NOT EDIT !! <<<<<<<<<<<<<<
*/

#ifndef	CONFIG_H
#define	CONFIG_H


/* build MINI KON */

/* Support VGA driver */
#define HAS_VGA

/* Support J31SX driver */

/* Support MOUSE driver */
#define HAS_MOUSE

/* Install Minix/V font loader */
#define FLD_MINIX

/* Install $fontx2 font loader */
#define FLD_BDF

/* Install .bdf font loader */
#define FLD_FONTX2

/* Install J3100ROM font loader */

/* Use ROM font */

/* Use Static font */
#define USE_STATICFONT
#endif

