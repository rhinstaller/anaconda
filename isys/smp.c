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

#ifdef __i386__
#define SMP_MAGIC_IDENT	(('_'<<24)|('P'<<16)|('M'<<8)|'_')

struct intel_mp_floating
{
	char mpf_signature[4];		/* "_MP_" 			*/
	unsigned long mpf_physptr;	/* Configuration table address	*/
	unsigned char mpf_length;	/* Our length (paragraphs)	*/
	unsigned char mpf_specification;/* Specification version	*/
	unsigned char mpf_checksum;	/* Checksum (makes sum 0)	*/
	unsigned char mpf_feature1;	/* Standard or configuration ? 	*/
	unsigned char mpf_feature2;	/* Bit7 set for IMCR|PIC	*/
	unsigned char mpf_feature3;	/* Unused (0)			*/
	unsigned char mpf_feature4;	/* Unused (0)			*/
	unsigned char mpf_feature5;	/* Unused (0)			*/
};

struct mp_config_table
{
	char mpc_signature[4];
#define MPC_SIGNATURE "PCMP"
	unsigned short mpc_length;	/* Size of table */
	char  mpc_spec;			/* 0x01 */
	char  mpc_checksum;
	char  mpc_oem[8];
	char  mpc_productid[12];
	unsigned long mpc_oemptr;	/* 0 if not present */
	unsigned short mpc_oemsize;	/* 0 if not present */
	unsigned short mpc_oemcount;
	unsigned long mpc_lapic;	/* APIC address */
	unsigned long reserved;
};

/* Followed by entries */

#define	MP_PROCESSOR	0
#define	MP_BUS		1
#define	MP_IOAPIC	2
#define	MP_INTSRC	3
#define	MP_LINTSRC	4

struct mpc_config_processor
{
	unsigned char mpc_type;
	unsigned char mpc_apicid;	/* Local APIC number */
	unsigned char mpc_apicver;	/* Its versions */
	unsigned char mpc_cpuflag;
#define CPU_ENABLED		1	/* Processor is available */
#define CPU_BOOTPROCESSOR	2	/* Processor is the BP */
	unsigned long mpc_cpufeature;		
#define CPU_STEPPING_MASK 0x0F
#define CPU_MODEL_MASK	0xF0
#define CPU_FAMILY_MASK	0xF00
	unsigned long mpc_featureflag;	/* CPUID feature value */
	unsigned long mpc_reserved[2];
};

struct mpc_config_bus
{
	unsigned char mpc_type;
	unsigned char mpc_busid;
	unsigned char mpc_bustype[6] __attribute((packed));
};

#define BUSTYPE_EISA	"EISA"
#define BUSTYPE_ISA	"ISA"
#define BUSTYPE_INTERN	"INTERN"	/* Internal BUS */
#define BUSTYPE_MCA	"MCA"
#define BUSTYPE_VL	"VL"		/* Local bus */
#define BUSTYPE_PCI	"PCI"
#define BUSTYPE_PCMCIA	"PCMCIA"

/* We don't understand the others */

struct mpc_config_ioapic
{
	unsigned char mpc_type;
	unsigned char mpc_apicid;
	unsigned char mpc_apicver;
	unsigned char mpc_flags;
#define MPC_APIC_USABLE		0x01
	unsigned long mpc_apicaddr;
};

struct mpc_config_intsrc
{
	unsigned char mpc_type;
	unsigned char mpc_irqtype;
	unsigned short mpc_irqflag;
	unsigned char mpc_srcbus;
	unsigned char mpc_srcbusirq;
	unsigned char mpc_dstapic;
	unsigned char mpc_dstirq;
};

#define MP_INT_VECTORED		0
#define MP_INT_NMI		1
#define MP_INT_SMI		2
#define MP_INT_EXTINT		3

#define MP_IRQDIR_DEFAULT	0
#define MP_IRQDIR_HIGH		1
#define MP_IRQDIR_LOW		3


struct mpc_config_intlocal
{
	unsigned char mpc_type;
	unsigned char mpc_irqtype;
	unsigned short mpc_irqflag;
	unsigned char mpc_srcbusid;
	unsigned char mpc_srcbusirq;
	unsigned char mpc_destapic;	
#define MP_APIC_ALL	0xFF
	unsigned char mpc_destapiclint;
};


/*
 *	Default configurations
 *
 *	1	2 CPU ISA 82489DX
 *	2	2 CPU EISA 82489DX no IRQ 8 or timer chaining
 *	3	2 CPU EISA 82489DX
 *	4	2 CPU MCA 82489DX
 *	5	2 CPU ISA+PCI
 *	6	2 CPU EISA+PCI
 *	7	2 CPU MCA+PCI
 */


static int smp_found_config=0;

/*
 *	Checksum an MP configuration block.
 */

static int mpf_checksum(unsigned char *mp, int len)
{
	int sum=0;
	while(len--)
		sum+=*mp++;
	return sum&0xFF;
}

static int do_smp_scan_config(unsigned long *bp, unsigned long length)
{
	struct intel_mp_floating *mpf;

/*
	if (sizeof(*mpf)!=16)
		logMessage("Error: MPF size\n");
*/

	while (length>0)
	{
		if (*bp==SMP_MAGIC_IDENT)
		{
			mpf=(struct intel_mp_floating *)bp;
			if (mpf->mpf_length==1 &&
				!mpf_checksum((unsigned char *)bp,16) &&
				(mpf->mpf_specification == 1
				 || mpf->mpf_specification == 4) )
			{
				/*logMessage("Intel MultiProcessor Specification v1.%d\n", mpf->mpf_specification);
				if (mpf->mpf_feature2&(1<<7))
					logMessage("    IMCR and PIC compatibility mode.\n");
				else
					logMessage("    Virtual Wire compatibility mode.\n");
*/
				smp_found_config=1;
				return 1;
			}
		}
		bp+=4;
		length-=16;
	}

	return 0;
}

static int smp_scan_config(int mem_fd, unsigned long base,
			   unsigned long length)
{
	void *p;
	int o;
	
	o=base&0xFFF;
	base-=o;
	length+=o;
	
	p=mmap(0, (length+4095)&0xFFFFF000,  PROT_READ, MAP_SHARED, 
		mem_fd, (base&0xFFFF0000));
	if(p==MAP_FAILED)
	{
		/*logMessage("SMP Probe error: mmap: %s", strerror(errno));*/
		return 1;
	}	
	do_smp_scan_config(p+o, length-o);
	munmap(p, (length+4095)&0xFFFFF000);
	return 0;
}

static int intelDetectSMP(void)
{
        int mem_fd;
        
	mem_fd=open("/dev/mem", O_RDONLY);
	
	if(mem_fd==-1)
	{
	        /*logMessage("Error detecting SMP: /dev/mem: %s", strerror(errno));*/
	}
	
	/*
	 * FIXME: Linux assumes you have 640K of base ram..
	 * this continues the error...
	 *
	 * 1) Scan the bottom 1K for a signature
	 * 2) Scan the top 1K of base RAM
	 * 3) Scan the 64K of bios
	 */
	if (!smp_scan_config(mem_fd, 0x0, 0x400) &&
	    !smp_scan_config(mem_fd, 639*0x400,0x400) &&
	    !smp_scan_config(mem_fd, 0xF0000,0x10000)) {
#if 0

		/*
		 * If it is an SMP machine we should know now, unless the
		 * configuration is in an EISA/MCA bus machine with an
		 * extended bios data area. 
		 *
		 * there is a real-mode segmented pointer pointing to the
		 * 4K EBDA area at 0x40E, calculate and scan it here.
		 *
		 * NOTE! There are Linux loaders that will corrupt the EBDA
		 * area, and as such this kind of SMP config may be less
		 * trustworthy, simply because the SMP table may have been
		 * stomped on during early boot. These loaders are buggy and
		 * should be fixed.
		 */
		unsigned int address;

		address = *(unsigned short *)phys_to_virt(0x40E);
		address<<=4;
		smp_scan_config(mem_fd, address, 0x1000);
		if (smp_found_config)
			/*logMessage("WARNING: MP table in the EBDA can be UNSAFE, contact linux-smp@vger.rutgers.edu if you experience SMP problems!\n");*/
#endif			
	}
/*
	if(smp_found_config)
		logMessage("Detected SMP capable motherboard\n");
	else
		logMessage("Detected non SMP capable motherboard\n");
*/
	return smp_found_config;
}
#endif /* __i386__ */

int detectSMP(void)
{
    static int isSMP = -1;

    if (isSMP != -1)
	return isSMP;

#ifdef __i386__
    return isSMP = intelDetectSMP();
#elif __sparc__
    return isSMP = sparcDetectSMP();
#elif __alpha__
    return isSMP = alphaDetectSMP();
#elif __ia64__
    return isSMP = 1;
#else
    #error unknown architecture
#endif
}
	
