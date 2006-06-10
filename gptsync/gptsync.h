/*
 * gptsync/gptsync.h
 * Common header for gptsync
 *
 * Copyright (c) 2006 Christoph Pfisterer
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the
 *    distribution.
 *
 *  * Neither the name of Christoph Pfisterer nor the names of the
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

//
// config
//

#ifdef EFI32
#define CONFIG_EFI
#endif

//
// types
//

#ifdef CONFIG_EFI

#include <efi.h>
#include <efilib.h>

#define copy_guid(destguid, srcguid) (CopyMem(destguid, srcguid, 16))
#define guids_are_equal(guid1, guid2) (CompareMem(guid1, guid2, 16) == 0)

typedef CHAR16 CHARN;
#define STR(x) L##x

#endif


#ifndef CONFIG_EFI

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#include <sys/types.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <fcntl.h>

typedef unsigned int        UINTN;
typedef unsigned char       UINT8;
typedef unsigned short      UINT16;
typedef unsigned long       UINT32;
typedef unsigned long long  UINT64;
typedef void                VOID;

typedef int                 BOOLEAN;
#ifndef FALSE
#define FALSE (0)
#endif
#ifndef TRUE
#define TRUE  (1)
#endif

typedef unsigned short      CHAR16;
typedef char                CHARN;
#define STR(x) x

void Print(wchar_t *format, ...);

// FUTURE: use STR(),  #define Print printf

#define CopyMem     memcpy
#define SetMem      memset
#define CompareMem  memcmp

#define copy_guid(destguid, srcguid) (memcpy(destguid, srcguid, 16))
#define guids_are_equal(guid1, guid2) (memcmp(guid1, guid2, 16) == 0)

#endif

//
// functions provided by the OS-specific module
//

UINTN read_sector(UINT64 lba, UINT8 *buffer);
UINTN write_sector(UINT64 lba, UINT8 *buffer);
UINTN input_boolean(CHARN *prompt, BOOLEAN *bool_out);

//
// common platform-independent function
//

UINTN gptsync(VOID);

/* EOF */
