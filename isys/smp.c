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
#include <limits.h>

#include "smp.h"

#ifdef DIET
typedef unsigned short u_short;
typedef unsigned long u_long;
typedef unsigned int u_int;
typedef unsigned char u_int8_t;
typedef unsigned short u_int16_t;
typedef unsigned int u_int32_t;
typedef unsigned long long u_int64_t;
#endif


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
    int ncpus = 0;
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
                            ncpus++;
                        }
                }
                fclose(f);
            }
        }

    return ncpus;
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
    u_char      oem_id[ 8 ];
    u_char      product_id[ 12 ];
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
#define MODE_SUMMIT_CHECK 2

static int groupForSMP(int mode)
{
    vm_offset_t paddr;
    int         where;
    mpfps_t     mpfps;
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
	ncpus = 2;
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

	if (mode == MODE_SUMMIT_CHECK) {
	    if (!strncmp(cth.oem_id, "IBM ENSW", 8) &&
		(!strncmp(cth.product_id, "NF 6000R", 8) ||
		 !strncmp(cth.product_id, "VIGIL SMP", 9) ||
		 !strncmp(cth.product_id, "EXA", 3) ||
		 !strncmp(cth.product_id, "RUTHLESS", 8)))
		return 1;
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
    }

    close (pfd);
    return ncpus;
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

    int         x;
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

#if defined(__i386__) || defined(__x86_64__)
#if defined(__x86_64__)
u_int32_t recursive_cpuid_eax(u_int32_t op, int cycle)
{
    u_int32_t saved_op=op, eax=op;
    u_int32_t out0, out1;

    /* just doing this once doesn't work on some SDP hardware.  doing it twice
       with a function call that has the output as an argument and manipulates
       the variable in some way seems to do it... -- pj
    */
    __asm__("cpuid"
            : "=a" (eax)
            : "0" (op)
            : "bx", "cx", "dx");
    out0 = eax;
    if (cycle != 0) {
        out1 = recursive_cpuid_eax(saved_op, 0);
        return out1 > out0 ? out1 : out0;
    }
    return out0;
}

#define cpuid_eax(x) recursive_cpuid_eax(x, 1)

u_int32_t cpuid_ebx(u_int32_t op)
{
    u_int32_t eax, ebx;
    __asm__("cpuid"
            : "=a" (eax), "=b" (ebx)
            : "0" (op)
            : "cx", "dx");
    return ebx;
}
u_int32_t cpuid_edx(u_int32_t op)
{
    u_int32_t eax, edx;
    __asm__("cpuid"
            : "=a" (eax), "=d" (edx)
            : "0" (op)
            : "bx", "cx");
    return edx;
}
#elif defined(__i386__)
static inline u_int32_t cpuid_eax(u_int32_t fn)
{
    u_int32_t eax, ebx;
    __asm__("pushl %%ebx; cpuid; movl %%eax,%[out]; popl %%ebx"
            : [out] "=a" (eax), "=g" (ebx)
            : "0" (fn)
            : "cx", "dx");
    return eax;
}
static inline u_int32_t cpuid_ebx(u_int32_t fn)
{
    u_int32_t eax, ebx;
    __asm__("pushl %%ebx; cpuid; movl %%ebx,%[out]; popl %%ebx"
            : "=a" (eax), [out] "=g" (ebx)
            : "0" (fn)
            : "cx", "dx");
    return ebx;
}
static inline u_int32_t cpuid_edx(u_int32_t fn)
{
    u_int32_t eax, ebx, edx;
    __asm__("pushl %%ebx; cpuid; movl %%edx,%[out]; popl %%ebx"
            : "=a" (eax), "=g" (ebx), [out] "=g" (edx)
            : "0" (fn)
            : "cx");
    return edx;
}
#endif

typedef enum {
    VENDOR_UNKNOWN,
    VENDOR_OTHER,
    VENDOR_INTEL,
    VENDOR_AMD,
} vendor_t;

vendor_t detectVendor(void)
{
    FILE *f;
    static vendor_t vendor = VENDOR_UNKNOWN;

    if (vendor != VENDOR_UNKNOWN)
        return vendor;
    vendor = VENDOR_OTHER;

    f = fopen("/proc/cpuinfo", "r");
    if (f) {
        char buf[1024] = {'\0'};

        while (fgets(buf, 1024, f) != NULL) {
            if (!strncmp(buf, "vendor_id\t: ", 12)) {
                if (!strncmp(buf+12, "GenuineIntel\n", 13))
                    vendor = VENDOR_INTEL;
                else if (!strncmp(buf+12, "AuthenticAMD\n", 13))
                    vendor = VENDOR_AMD;
            }
        }
        fclose(f);
    }

    return vendor;
}

int detectHT(void)
{
    u_int32_t ebx = 0;
    int logical_procs = 0;

    ebx = cpuid_ebx(1);
    logical_procs = (ebx & 0xff0000) >> 16;

    return logical_procs;
}

int detectCoresPerPackage(void)
{
    int cores_per_package = 1;
    vendor_t vendor = detectVendor();

    switch (vendor) {
        case VENDOR_INTEL: {
                /* <geoff> cpuid eax=04h returns cores per physical package
                           in eax[31-26]+1 (i.e. 0 for 1, 1 for 2) */
                u_int32_t eax = 0;

                eax = cpuid_eax(4);
                cores_per_package = ((eax & 0xfc000000) >> 26) + 1;
                break;
            }
        case VENDOR_AMD: {
                u_int32_t edx = 0;

                edx = cpuid_edx(0x80000008);
                cores_per_package = (edx & 0xff) + 1;
                break;
            }
        case VENDOR_OTHER:
        default:
            break;
    }
    return cores_per_package;
}

int detectSummit(void)
{
    return groupForSMP(MODE_SUMMIT_CHECK);
}

#elif defined (__ia64__)

int detectHT(void)
{
    long nthreads = 0;
    FILE *f;
    
    f = fopen("/proc/cpuinfo", "r");
    if (f) {     
        char buf[1024];

        while (fgets(buf, 1024, f) != NULL) {
            if (!strncmp(buf, "siblings   : ", 13)) {
                errno = 0;
                nthreads = strtol(buf+13, NULL, 0);
                if (nthreads == LONG_MAX || nthreads == LONG_MIN || errno)
                    nthreads = 1;
                break;
            }
        }
        fclose(f);
    } else
        return 1;
    return nthreads ? nthreads : 1;
}

struct dmi_header {
    u_int8_t type;
    u_int8_t length;
    u_int16_t handle;
};

static int checksum(const u_int8_t *buf, size_t len)
{
	u_int8_t sum=0;
	size_t a;
	
	for(a=0; a<len; a++)
		sum+=buf[a];
	return (sum==0);
}

static void *mem_chunk(size_t base, size_t len, const char *devmem)
{
	void *p;
	int fd;
	size_t mmoffset;
	void *mmp;
	
	if((fd=open(devmem, O_RDONLY))==-1)
	{
		perror(devmem);
		return NULL;
	}
	
	if((p=malloc(len))==NULL)
	{
		perror("malloc");
		return NULL;
	}
	
#ifdef _SC_PAGESIZE
	mmoffset=base%sysconf(_SC_PAGESIZE);
#else
	mmoffset=base%getpagesize();
#endif /* _SC_PAGESIZE */
	/*
	 * Please note that we don't use mmap() for performance reasons here,
	 * but to workaround problems many people encountered when trying
	 * to read from /dev/mem using regular read() calls.
	 */
	mmp=mmap(0, mmoffset+len, PROT_READ, MAP_SHARED, fd, base-mmoffset);
	if(mmp==MAP_FAILED)
	{
		free(p);
		return NULL;
	}
	
	memcpy(p, (u_int8_t *)mmp+mmoffset, len);

	munmap(mmp, mmoffset+len);

	close(fd);

	return p;
}

static int dmi_table(u_int32_t base, u_int16_t len, u_int16_t num,
        u_int16_t ver, const char *devmem)
{
    u_int8_t *buf;
    u_int8_t *data;
    int i = 0;
    int ncpus=0;

    if ((buf=mem_chunk(base, len, devmem))==NULL)
        return 0;

    data = buf;
    while (i<num && data+sizeof (struct dmi_header) <= buf+len) {
        u_int8_t *next;
        struct dmi_header *h = (struct dmi_header *)data;

        next = data + h->length;
        while(next-buf+1 < len && (next[0]!=0 || next[1]!=0))
            next++;
	next += 2;

        /* type "socket" && populated */
        if (h->type == 4 && (data[0x18] & (1<<6))) {
            u_int8_t code = data[0x18] & 0x07;

            /* not disabled */
            if (code != 0x02 && code != 0x03)
                ncpus++;
        }

        data = next;
        i++;
    }
    free(buf);
    return ncpus;
}

#define WORD(x) (u_int16_t)(*(const u_int16_t *)(x))
#define DWORD(x) (u_int32_t)(*(const u_int32_t *)(x))

#include <inttypes.h>

static int smbios_decode(u_int8_t *buf, const char *devmem)
{
    if (checksum(buf, buf[0x05]) && memcmp(buf+0x10, "_DMI_", 5) == 0 \
            && checksum(buf+0x10, 0x0f)) {
        return dmi_table(DWORD(buf+0x18), WORD(buf+0x16), WORD(buf+0x1c),
                (buf[0x06]<<4) + buf[0x07], devmem);
    }
    return 0;
}

int ia64DetectSMP(void)
{
    FILE *efi_systab;
    const char *filename;
    char linebuf[64];
    size_t fp;
    u_int8_t *buf;
    int ncpus=0;

    if ((efi_systab=fopen(filename="/proc/efi/systab", "r"))==NULL &&
            (efi_systab=fopen(filename="/sys/firmware/efi/systab", "r"))==NULL)
        return 0;

    fp = 0;
    while((fgets(linebuf, sizeof(linebuf)-1, efi_systab))!=NULL) {
        char *addr = memchr(linebuf, '=', strlen(linebuf));
        *(addr++)='\0';
        
        if (strcmp(linebuf, "SMBIOS")==0)
            fp = strtoul(addr, NULL, 0);
    }
    fclose(efi_systab);
    if (fp == 0)
        return 0;

    buf = mem_chunk(fp, 0x20, "/dev/mem");
    if (!buf)
        return 0;

    ncpus = smbios_decode(buf, "/dev/mem");
    free(buf);

    return ncpus;
}

int detectSummit(void)
{
    return 0;
}

#else /* ndef __i386__ */

int detectHT(void)
{
    return 0;
}

int detectSummit(void)
{
    return 0;
}

#endif /* __i386__ */

#if !defined(__i386__) && !defined(__x86_64__)
int detectCoresPerPackage(void)
{
    return 1;
}
#endif

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
#elif defined (__ia64__)
    return isSMP = ia64DetectSMP();
#elif defined (__powerpc__)
    return isSMP = powerpcDetectSMP();
#else
    #error unknown architecture
#endif
}
