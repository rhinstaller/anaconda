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
#include	<stdlib.h>
#include	<sys/types.h>
#include	<sys/ipc.h>
#include	<sys/shm.h>
#include	<sys/socket.h>
#include	<errno.h>

#include	<fnld.h>
#include	<interface.h>

#ifndef	MINI_KON

void DownShmem(char fnum)
{
    key_t shmkey;
    int	shmid;
    struct shmid_ds shmseg;

#if defined(linux)
    shmkey = ftok(CONFIG_NAME, fnum);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fnum & 0x7F);
#endif
    if ((shmid = shmget(shmkey, sizeof(struct fontInfo), 0444)) < 0)
	return;
    shmctl(shmid, IPC_STAT, &shmseg);
    if (shmseg.shm_nattch < 1) {
	shmctl(shmid, IPC_RMID, 0);
    }
}

u_char	*GetShmem(fnum)
char	fnum;
{
    key_t shmkey;
    int shmid;

#if defined(linux)
    shmkey = ftok(CONFIG_NAME, fnum);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fnum & 0x7F);
#endif
    if ((shmid = shmget(shmkey, sizeof(struct fontInfo), 0444)) < 0) return(0);
    return((u_char*)shmat(shmid, 0, SHM_RDONLY));
}

#endif
