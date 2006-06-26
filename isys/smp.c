/*
[_Anarchy_(alan@lightning.swansea.uk.linux.org)] you should do one check
   though - if the board seems to be SMP and the CPU in /proc/cpuinfo is non
   intel dont install an SMP kernel - thats a dual pentium board with a cyrix
   or similar single cpu in it
*/


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <string.h>
#include <errno.h>
#include <stdint.h>
#include <sys/types.h>

#ifdef __alpha__
int alphaDetectSMP(void)
{
    int issmp = 0;
    FILE *f;
    
    f = fopen("/proc/cpuinfo", "r");
    if (f) {     
	char buff[1024];
	
	while (fgets (buff, 1024, f) != NULL) {
	    if (!strncmp (buff, "cpus detected\t\t: ", 17)) {
		if (strtoul (buff + 17, NULL, 0) > 1)
		    issmp = 1;
		break;
	    }
	}
	fclose(f);
    } else
	return -1;
    
    return issmp;
}
#endif /* __alpha__ */


#if defined (__s390__) || defined (__s390x__)
int s390DetectSMP(void)
{
    int issmp = 0;
    FILE *f;

    f = fopen("/proc/cpuinfo", "r");
    if (f) {
        char buff[1024];

        while (fgets (buff, 1024, f) != NULL) {
            if (!strncmp (buff, "# processors    : ", 18)) {
                if (strtoul (buff + 18, NULL, 0) > 1)
                    issmp = 1;
                break;
            }
        }
        fclose(f);
    } else
        return -1;

    return issmp;
}
#endif /* __s390__ */

#ifdef __sparc__
int sparcDetectSMP(void)
{
    int issmp = 0;
    FILE *f;
    
    f = fopen("/proc/cpuinfo", "r");
    if (f) {     
	char buff[1024];
	
	while (fgets (buff, 1024, f) != NULL) {
	    if (!strncmp (buff, "ncpus probed\t: ", 15)) {
		if (strtoul (buff + 15, NULL, 0) > 1)
		    issmp = 1;
		break;
	    }
	}
	fclose(f);
    } else
	return -1;
    
    return issmp;
}
#endif /* __sparc__ */

#ifdef __powerpc__
#include "minifind.h"

/* FIXME: this won't work on iSeries */
int powerpcDetectSMP(void)
{
    int issmp = -1;
    FILE *f;
    struct findNode *list = (struct findNode *) malloc(sizeof(struct findNode));
    struct pathNode *n;
        
    list->result = (struct pathNode *) malloc(sizeof(struct pathNode));
    list->result->path = NULL;
    list->result->next = list->result;
        
    minifind("/proc/device-tree/cpus", "device_type", list);
              
    for (n = list->result->next; n != list->result; n = n->next)
        {
            f = fopen(n->path, "r");
            if (f) {
                char buff[1024];
                while (fgets (buff, 1024, f) !=  NULL) {
                    if (!strncmp (buff, "cpu", 3))
                        {
                            issmp++;
                            break;
                        }
                }
                fclose(f);
            }
        }

    return issmp;
}
#endif /* __powerpc__ */

#if defined(__i386__) || defined(__x86_64__)
/*
 * Copyright (c) 1996, by Steve Passe
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. The name of the developer may NOT be used to endorse or promote products
 *    derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 *      $Id$
 */

/*
 * mptable.c
 */

#define VMAJOR                  2
#define VMINOR                  0
#define VDELTA                  12

/*
 * this will cause the raw mp table to be dumped to /tmp/mpdump
 *
#define RAW_DUMP
 */

#define MP_SIG                  0x5f504d5f      /* _MP_ */
#define EXTENDED_PROCESSING_READY
#define OEM_PROCESSING_READY_NOT

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>

#define LINUX 1
#if LINUX
typedef uint32_t vm_offset_t;
#else
#include <machine/types.h>
#endif

/* EBDA is @ 40:0e in real-mode terms */
#define EBDA_POINTER            0x040e          /* location of EBDA pointer */

/* CMOS 'top of mem' is @ 40:13 in real-mode terms */
#define TOPOFMEM_POINTER        0x0413          /* BIOS: base memory size */

#define DEFAULT_TOPOFMEM        0xa0000

#define BIOS_BASE               0xf0000
#define BIOS_BASE2              0xe0000
#define BIOS_SIZE               0x10000
#define ONE_KBYTE               1024

#define GROPE_AREA1             0x80000
#define GROPE_AREA2             0x90000
#define GROPE_SIZE              0x10000

/* MP Floating Pointer Structure */
typedef struct MPFPS {
    char        signature[ 4 ];
    int32_t     pap;
    u_char      length;
    u_char      spec_rev;
    u_char      checksum;
    u_char      mpfb1;
    u_char      mpfb2;
    u_char      mpfb3;
    u_char      mpfb4;
    u_char      mpfb5;
} mpfps_t;

/* MP Configuration Table Header */
typedef struct MPCTH {
    char        signature[ 4 ];
    uint16_t    base_table_length;
    u_char      spec_rev;
    u_char      checksum;
    char        oem_id[ 8 ];
    char        product_id[ 12 ];
    int32_t     oem_table_pointer;
    uint16_t    oem_table_size;
    uint16_t    entry_count;
    int32_t     apic_address;
    uint16_t    extended_table_length;
    u_char      extended_table_checksum;
    u_char      reserved;
} mpcth_t;

typedef struct PROCENTRY {
    u_char      type;
    u_char      apicID;
    u_char      apicVersion;
    u_char      cpuFlags;
    uint32_t    cpuSignature;
    uint32_t    featureFlags;
    uint32_t    reserved1;
    uint32_t    reserved2;
} ProcEntry;

#define PROCENTRY_FLAG_EN       0x01

static int seekEntry( vm_offset_t addr );
static void apic_probe( vm_offset_t* paddr, int* where );
static void readEntry( void* entry, int size );

/* global data */
static int     pfd;            /* physical /dev/mem fd */
static int     verbose = 0;
static int     grope = 0;

static int
readType()
{
    u_char      type;

    if ( read( pfd, &type, sizeof( u_char ) ) != sizeof( u_char ) ) {
/*         perror( "type read" ); */
/*         fprintf( stderr, "\npfd: %d", pfd ); */
/*         fflush( stderr ); */
/*         exit( 1 ); */
	return -1;
    }

    if ( lseek( pfd, -1, SEEK_CUR ) < 0 ) {
/*         perror( "type seek" ); */
/*         exit( 1 ); */
	return -1;
    }

    return (int)type;
}

#define MODE_SMP_CHECK 1

static int groupForSMP(int mode)
{
    vm_offset_t paddr;
    int         where;
    mpfps_t     mpfps;
    int		rc = 0;
    int		ncpus = 0;
        
    /* open physical memory for access to MP structures */
    if ( (pfd = open( "/dev/mem", O_RDONLY )) < 0 ) {
	return 0;
    }

    /* probe for MP structures */
    apic_probe( &paddr, &where );
    if ( where <= 0 )
	return 0;

    if (seekEntry( paddr ))
	return 0;
    readEntry( &mpfps, sizeof( mpfps_t ) );

    if (mpfps.mpfb1)
	/* old style */
	rc = 1;
    else {
	/* go to the config table */
	mpcth_t     cth;
	int count, i;
	    
	paddr = (vm_offset_t) mpfps.pap;
	if (seekEntry( paddr ))
	    return 0;
	readEntry( &cth, sizeof( cth ) );
	/* if we don't have any entries, the kernel sure
	   won't be able to set up mp.  Needs at least one entry
	   for smp kernel */
	if (cth.entry_count <= 1) {
	    close (pfd);
	    return 0;
	}

	count = cth.entry_count;
	for (i = 0; i < count; i++) {
	    if ( readType() == 0 ) {
		ProcEntry   entry;
		readEntry( &entry, sizeof( entry ) );
		if (entry.cpuFlags & PROCENTRY_FLAG_EN)
		    ncpus++;
	    }
	}
	if (ncpus > 1)
	    rc = 1;
    }

    close (pfd);
    return rc;
}

/*
 * set PHYSICAL address of MP floating pointer structure
 */
#define NEXT(X)         ((X) += 4)
static void
apic_probe( vm_offset_t* paddr, int* where )
{
    /*
     * c rewrite of apic_probe() by Jack F. Vogel
     */

    unsigned int         x;
    uint16_t     segment;
    vm_offset_t target;
    uint32_t       buffer[ BIOS_SIZE / sizeof( int32_t ) ];

    if ( verbose )
        printf( "\n" );

    /* search Extended Bios Data Area, if present */
    if ( verbose )
        printf( " looking for EBDA pointer @ 0x%04x, ", EBDA_POINTER );
    if (seekEntry( (vm_offset_t)EBDA_POINTER )) {
	*where = 0;
	*paddr = (vm_offset_t)0;
	return;
    }
    readEntry( &segment, 2 );
    if ( segment ) {                /* search EBDA */
        target = (vm_offset_t)segment << 4;
        if ( verbose )
            printf( "found, searching EBDA @ 0x%08x\n", target );
        if (seekEntry( target )) {
	    *where = 0;
	    *paddr = (vm_offset_t)0;
	    return;
	}
        readEntry( buffer, ONE_KBYTE );

        for ( x = 0; x < ONE_KBYTE / sizeof ( uint32_t ); NEXT(x) ) {
            if ( buffer[ x ] == MP_SIG ) {
                *where = 1;
                *paddr = (x * sizeof( uint32_t )) + target;
                return;
            }
        }

    }
    else {
        if ( verbose )
            printf( "NOT found\n" );
    }

    /* read CMOS for real top of mem */
    if (seekEntry( (vm_offset_t)TOPOFMEM_POINTER )) {
	*where = 0;
	*paddr = (vm_offset_t)0;
	return;
    }
    readEntry( &segment, 2 );
    --segment;                                          /* less ONE_KBYTE */
    target = segment * 1024;
    if ( verbose )
        printf( " searching CMOS 'top of mem' @ 0x%08x (%dK)\n",
                target, segment );
    seekEntry( target );
    readEntry( buffer, ONE_KBYTE );

    for ( x = 0; x < ONE_KBYTE / sizeof ( uint32_t ); NEXT(x) ) {
        if ( buffer[ x ] == MP_SIG ) {
            *where = 2;
            *paddr = (x * sizeof( uint32_t )) + target;
            return;
        }
    }

    /* we don't necessarily believe CMOS, check base of the last 1K of 640K */
    if ( target != (DEFAULT_TOPOFMEM - 1024)) {
        target = (DEFAULT_TOPOFMEM - 1024);
        if ( verbose )
            printf( " searching default 'top of mem' @ 0x%08x (%dK)\n",
                    target, (target / 1024) );
        seekEntry( target );
        readEntry( buffer, ONE_KBYTE );

        for ( x = 0; x < ONE_KBYTE / sizeof ( uint32_t ); NEXT(x) ) {
            if ( buffer[ x ] == MP_SIG ) {
                *where = 3;
                *paddr = (x * sizeof( uint32_t )) + target;
                return;
            }
        }
    }

    /* search the BIOS */
    if ( verbose )
        printf( " searching BIOS @ 0x%08x\n", BIOS_BASE );
    seekEntry( BIOS_BASE );
    readEntry( buffer, BIOS_SIZE );

    for ( x = 0; x < BIOS_SIZE / sizeof( uint32_t ); NEXT(x) ) {
        if ( buffer[ x ] == MP_SIG ) {
            *where = 4;
            *paddr = (x * sizeof( uint32_t )) + BIOS_BASE;
            return;
        }
    }

    /* search the extended BIOS */
    if ( verbose )
        printf( " searching extended BIOS @ 0x%08x\n", BIOS_BASE2 );
    seekEntry( BIOS_BASE2 );
    readEntry( buffer, BIOS_SIZE );

    for ( x = 0; x < BIOS_SIZE / sizeof( uint32_t ); NEXT(x) ) {
        if ( buffer[ x ] == MP_SIG ) {
            *where = 5;
            *paddr = (x * sizeof( uint32_t )) + BIOS_BASE2;
            return;
        }
    }

    if ( grope ) {
        /* search additional memory */
        target = GROPE_AREA1;
        if ( verbose )
            printf( " groping memory @ 0x%08x\n", target );
        seekEntry( target );
        readEntry( buffer, GROPE_SIZE );

        for ( x = 0; x < GROPE_SIZE / sizeof( uint32_t ); NEXT(x) ) {
            if ( buffer[ x ] == MP_SIG ) {
                *where = 6;
                *paddr = (x * sizeof( uint32_t )) + GROPE_AREA1;
                return;
            }
        }

        target = GROPE_AREA2;
        if ( verbose )
            printf( " groping memory @ 0x%08x\n", target );
        seekEntry( target );
        readEntry( buffer, GROPE_SIZE );

        for ( x = 0; x < GROPE_SIZE / sizeof( uint32_t ); NEXT(x) ) {
            if ( buffer[ x ] == MP_SIG ) {
                *where = 7;
                *paddr = (x * sizeof( uint32_t )) + GROPE_AREA2;
                return;
            }
        }
    }

    *where = 0;
    *paddr = (vm_offset_t)0;
}


/*
 *
 */
static int
seekEntry( vm_offset_t addr )
{
    if ( lseek( pfd, (off_t)addr, SEEK_SET ) < 0 ) {
        return 1;
    }
    return 0;
}


/*
 *
 */
static void
readEntry( void* entry, int size )
{
    if ( read( pfd, entry, size ) != size ) {
        return;
        perror( "readEntry" );
        exit( 1 );
    }
}

static int intelDetectSMP(void)
{
    return groupForSMP(MODE_SMP_CHECK);
}

/* ---- end mptable mess ---- */
#endif /* __i386__ || __x86_64__ */

#if defined(__i386__)
static inline unsigned int cpuid_ebx(int op)
{
    unsigned int eax, ebx;

    __asm__("pushl %%ebx; cpuid; movl %%ebx,%1; popl %%ebx"
            : "=a" (eax), "=g" (ebx)
            : "0" (op)
            : "cx", "dx");
    return ebx;
}
#elif defined(__x86_64__)
static inline unsigned int cpuid_ebx(int op)
{
    unsigned int eax, ebx;

    __asm__("cpuid"
            : "=a" (eax), "=b" (ebx)
            : "0" (op)
            : "cx", "dx");
    return ebx;
}
#endif

#if defined(__i386__) || defined(__x86_64__)
/* XXX: rewrite using /proc/cpuinfo info if it there.  Only fall
   back to inline asm if it is not */
int detectHT(void)
{
    FILE *f;
    int htflag = 0;
    uint32_t ebx = 0;
    int smp_num_siblings = 0;
    
    f = fopen("/proc/cpuinfo", "r");
    if (f) {
	char buff[1024];
	
	while (fgets (buff, 1024, f) != NULL) {
	    if (!strncmp (buff, "flags\t\t:", 8)) {
		if (strstr(buff, " ht ") ||
		    /* buff includes \n, so back up 4 bytes from the end
		       and check there too to catch the end case */
		    !strncmp(buff + strlen(buff) - 4, " ht", 3)) {
		    htflag = 1;
		}
		break;
	    }
	}
	fclose(f);
    }
    if (!htflag)
	return 0;

    ebx = cpuid_ebx(1);
    smp_num_siblings = (ebx & 0xff0000) >> 16;
    
    if (smp_num_siblings >= 2)
	return 1;
    return 0;
}

#else /* ndef __i386__ */

int detectHT(void)
{
    return 0;
}

#endif /* __i386__ */

int detectSMP(void)
{
    static int isSMP = -1;

    if (isSMP != -1)
	return isSMP;

#if defined (__i386__) || defined(__x86_64__)
    return isSMP = intelDetectSMP();
#elif defined (__sparc__)
    return isSMP = sparcDetectSMP();
#elif defined (__alpha__)
    return isSMP = alphaDetectSMP();
#elif defined (__s390__) || defined (__s390x__)
    return isSMP = s390DetectSMP();
#elif defined (__ia64__) || defined (__x86_64__)
    return isSMP = 1;
#elif defined (__powerpc__)
    return isSMP = powerpcDetectSMP();
#else
    #error unknown architecture
#endif
}
