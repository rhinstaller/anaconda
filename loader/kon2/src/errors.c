/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1993 by MAEDA Atusi (mad@math.keio.ac.jp)
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
 * THIS SOFTWARE IS PROVIDED BY MAEDA ATUSI ``AS IS'' AND ANY
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
#include	<stdarg.h>
#include	<stdlib.h>
#include	<string.h>
#include	<sys/types.h>

#include	<defs.h>
#include	<errors.h>
#include	<vc.h>
#include	<vt.h>

#define MAX_MSGLEN 1024

static void KonPrintf(const char *head, const char *format, va_list args)
{
#ifndef MINI_KON
	char buf[MAX_MSGLEN];

	if (con.text_mode) {
		fprintf(stderr, "%s", head);
		vfprintf(stderr, format, args);
	} else {
		VtEmu(head, strlen(head));
		vsprintf(buf, format, args);
		VtEmu(buf, strlen(buf));
	}
#endif
}

void fatal(const char *format, ...)
{
#ifndef MINI_KON
	va_list args;

	va_start(args, format);
	fprintf(stderr, "KON> fatal error: ");
	vfprintf(stderr, format, args);
	va_end(args);
#endif
	exit(EXIT_FAILURE);
}

void warn(const char *format, ...)
{
	va_list args;

	va_start(args, format);
	KonPrintf("KON> warning: ", format, args);
	va_end(args);
}

void kon_error(const char *format, ...)
{
#ifndef MINI_KON
	va_list args;

	va_start(args, format);
	KonPrintf("KON> error: ", format, args);
	va_end(args);
#endif
}

void message(const char *format, ...)
{
#ifndef MINI_KON
	va_list args;

	va_start(args, format);
	KonPrintf("KON> ", format, args);
	va_end(args);
#endif
}

void Perror(const char *msg)
{
#ifndef MINI_KON
	message("system error - %s: %s\r\n", msg, strerror(errno));
#endif
}

void PerrorExit(const char *message)
{
#ifndef MINI_KON
	fprintf(stderr, "%s: %s\r\n", message, strerror(errno));
#endif
	exit(EXIT_FAILURE);
}
