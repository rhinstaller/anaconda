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

/* getcap library - read configuration file and invoke initializer function */

#ifndef GETCAP_H
#define GETCAP_H

#include	<defs.h>

/* Initializer function should return 0 on success, -1 on failure. */
typedef int	(initializer)(const char *);

/* Define initializer function func for capability name.  If def_value is nil,
   then the entry of the name must exist in configuration file.  An error is
   flagged if no entry is found.  If def_value is non-nil and no entry is found
   in configuration file, then func is invoked with def_value. */
extern void	DefineCap(const char *name, initializer *func, const char *def_value);

/* Delete all initializer functions. */
extern void	CapInit(void);

/* Read configuration file named filename and invoke initializer function for each entry.
   Return 0 on success, -1 on failure. */
extern int	ReadConfig(const char *filename);

/* Set value for capability capName.  Return 0 on success, -1 if capName not defined. */
extern int	SetCapArg(const char *capName, const char *value);

#define	MAX_COLS	256		 /* maximum line length of config file */

/* Utility function that return 1 if confstr is "On" and 0 if "OFF". */
extern bool BoolConf(const char *confstr);

#endif
