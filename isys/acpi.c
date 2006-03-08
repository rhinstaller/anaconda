
#undef ANACONDA_COUNT_MISSING_HOTPLUGGABLE_CPUS

#include <sys/types.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <unistd.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>

#if defined(__x86_64__) || defined(__i386__)

#define APIC_DEFAULT_PHYS_BASE 0xfee00000

#ifdef DIET
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;
#else
typedef u_int64_t u64;
typedef u_int32_t u32;
typedef u_int16_t u16;
typedef u_int8_t u8;
#endif

#define phys_to_virt(a) (a)
#define __va(a) ((void *)a)
#define __pa(a) ((void *)a)

#define __init
#define __initdata
#if 0
#define printk(...) printf(__VA_ARGS__)
#else
#define printk(...)
#endif
#define KERN_WARNING ""
#define KERN_ERR ""
#define KERN_DEBUG ""
#define KERN_INFO

static const int efi_enabled = 0;
static const struct {
    unsigned long acpi20;
    unsigned long acpi;
} efi = {0,0};

static struct acpi_table_rsdp *rsdp = NULL;

static void mp_register_lapic(u8 id, u8 enabled);

static void *mem_chunk(size_t base, size_t len, const char *devmem)
{
	void *p;
	int fd;
	size_t mmoffset;
	void *mmp;
        size_t pgsz;

#ifdef _SC_PAGESIZE
	pgsz = sysconf(_SC_PAGESIZE);
#else
	pgsz = getpagesize();
#endif /* _SC_PAGESIZE */

        len = (len + (pgsz-1)) & ~(pgsz-1);
        
	if((fd=open(devmem, O_RDONLY))==-1)
	{
		//perror(devmem);
		return NULL;
	}
	
	if((p=malloc(len))==NULL)
	{
		//perror("malloc");
		return NULL;
	}
	printk("%d allocated %ld at %p\n", __LINE__, len, p);
	
        mmoffset = base % pgsz;
	/*
	 * Please note that we don't use mmap() for performance reasons here,
	 * but to workaround problems many people encountered when trying
	 * to read from /dev/mem using regular read() calls.
	 */
	mmp=mmap(0, mmoffset+len, PROT_READ, MAP_SHARED, fd, base-mmoffset);
	if(mmp==MAP_FAILED)
	{
		printk("%d freeing %p\n", __LINE__, p);
		free(p);
		return NULL;
	}
	
	memcpy(p, (u8 *)mmp+mmoffset, len);

	munmap(mmp, mmoffset+len);

	close(fd);

	return p;
}

#include "acpi/actbl.h"

/* Root System Description Pointer (RSDP) */

struct acpi_table_rsdp {
	char			signature[8];
	u8			checksum;
	char			oem_id[6];
	u8			revision;
	u32			rsdt_address;
} __attribute__ ((packed));

struct acpi20_table_rsdp {
	char			signature[8];
	u8			checksum;
	char			oem_id[6];
	u8			revision;
	u32			rsdt_address;
	u32			length;
	u64			xsdt_address;
	u8			ext_checksum;
	u8			reserved[3];
} __attribute__ ((packed));

typedef struct {
	u8			type;
	u8			length;
} __attribute__ ((packed)) acpi_table_entry_header;

/* Root System Description Table (RSDT) */

struct acpi_table_rsdt {
	struct acpi_table_header header;
	u32			entry[8];
} __attribute__ ((packed));

/* Extended System Description Table (XSDT) */

struct acpi_table_xsdt {
	struct acpi_table_header header;
	u64			entry[1];
} __attribute__ ((packed));

/* Fixed ACPI Description Table (FADT) */

struct acpi_table_fadt {
	struct acpi_table_header header;
	u32 facs_addr;
	u32 dsdt_addr;
	/* ... */
} __attribute__ ((packed));

/* Multiple APIC Description Table (MADT) */

struct acpi_table_madt {
	struct acpi_table_header header;
	u32			lapic_address;
	struct {
		u32			pcat_compat:1;
		u32			reserved:31;
	}			flags;
} __attribute__ ((packed));

enum acpi_madt_entry_id {
	ACPI_MADT_LAPIC = 0,
	ACPI_MADT_IOAPIC,
	ACPI_MADT_INT_SRC_OVR,
	ACPI_MADT_NMI_SRC,
	ACPI_MADT_LAPIC_NMI,
	ACPI_MADT_LAPIC_ADDR_OVR,
	ACPI_MADT_IOSAPIC,
	ACPI_MADT_LSAPIC,
	ACPI_MADT_PLAT_INT_SRC,
	ACPI_MADT_ENTRY_COUNT
};

typedef struct {
	u16			polarity:2;
	u16			trigger:2;
	u16			reserved:12;
} __attribute__ ((packed)) acpi_interrupt_flags;

struct acpi_table_lapic {
	acpi_table_entry_header	header;
	u8			acpi_id;
	u8			id;
	struct {
		u32			enabled:1;
		u32			reserved:31;
	}			flags;
} __attribute__ ((packed));

struct acpi_table_ioapic {
	acpi_table_entry_header	header;
	u8			id;
	u8			reserved;
	u32			address;
	u32			global_irq_base;
} __attribute__ ((packed));

struct acpi_table_int_src_ovr {
	acpi_table_entry_header	header;
	u8			bus;
	u8			bus_irq;
	u32			global_irq;
	acpi_interrupt_flags	flags;
} __attribute__ ((packed));

struct acpi_table_nmi_src {
	acpi_table_entry_header	header;
	acpi_interrupt_flags	flags;
	u32			global_irq;
} __attribute__ ((packed));

struct acpi_table_lapic_nmi {
	acpi_table_entry_header	header;
	u8			acpi_id;
	acpi_interrupt_flags	flags;
	u8			lint;
} __attribute__ ((packed));

struct acpi_table_lapic_addr_ovr {
	acpi_table_entry_header	header;
	u8			reserved[2];
	u64			address;
} __attribute__ ((packed));

struct acpi_table_iosapic {
	acpi_table_entry_header	header;
	u8			id;
	u8			reserved;
	u32			global_irq_base;
	u64			address;
} __attribute__ ((packed));

struct acpi_table_lsapic {
	acpi_table_entry_header	header;
	u8			acpi_id;
	u8			id;
	u8			eid;
	u8			reserved[3];
	struct {
		u32			enabled:1;
		u32			reserved:31;
	}			flags;
} __attribute__ ((packed));

struct acpi_table_plat_int_src {
	acpi_table_entry_header	header;
	acpi_interrupt_flags	flags;
	u8			type;	/* See acpi_interrupt_type */
	u8			id;
	u8			eid;
	u8			iosapic_vector;
	u32			global_irq;
	struct {
		u32			cpei_override_flag:1;
		u32			reserved:31;
	}			plint_flags;
} __attribute__ ((packed));

enum acpi_interrupt_id {
	ACPI_INTERRUPT_PMI	= 1,
	ACPI_INTERRUPT_INIT,
	ACPI_INTERRUPT_CPEI,
	ACPI_INTERRUPT_COUNT
};

#define	ACPI_SPACE_MEM		0

struct acpi_gen_regaddr {
	u8  space_id;
	u8  bit_width;
	u8  bit_offset;
	u8  resv;
	u32 addrl;
	u32 addrh;
} __attribute__ ((packed));

struct acpi_table_hpet {
	struct acpi_table_header header;
	u32 id;
	struct acpi_gen_regaddr addr;
	u8 number;
	u16 min_tick;
	u8 page_protect;
} __attribute__ ((packed));

/*
 * Simple Boot Flags
 * http://www.microsoft.com/whdc/hwdev/resources/specs/simp_bios.mspx
 */
struct acpi_table_sbf
{
	u8 sbf_signature[4];
	u32 sbf_len;
	u8 sbf_revision;
	u8 sbf_csum;
	u8 sbf_oemid[6];
	u8 sbf_oemtable[8];
	u8 sbf_revdata[4];
	u8 sbf_creator[4];
	u8 sbf_crearev[4];
	u8 sbf_cmos;
	u8 sbf_spare[3];
} __attribute__ ((packed));

/*
 * System Resource Affinity Table (SRAT)
 * http://www.microsoft.com/whdc/hwdev/platform/proc/SRAT.mspx
 */

struct acpi_table_srat {
	struct acpi_table_header header;
	u32			table_revision;
	u64			reserved;
} __attribute__ ((packed));

enum acpi_srat_entry_id {
	ACPI_SRAT_PROCESSOR_AFFINITY = 0,
	ACPI_SRAT_MEMORY_AFFINITY,
	ACPI_SRAT_ENTRY_COUNT
};

struct acpi_table_processor_affinity {
	acpi_table_entry_header	header;
	u8			proximity_domain;
	u8			apic_id;
	struct {
		u32			enabled:1;
		u32			reserved:31;
	}			flags;
	u8			lsapic_eid;
	u8			reserved[7];
} __attribute__ ((packed));

struct acpi_table_memory_affinity {
	acpi_table_entry_header	header;
	u8			proximity_domain;
	u8			reserved1[5];
	u32			base_addr_lo;
	u32			base_addr_hi;
	u32			length_lo;
	u32			length_hi;
	u32			memory_type;	/* See acpi_address_range_id */
	struct {
		u32			enabled:1;
		u32			hot_pluggable:1;
		u32			reserved:30;
	}			flags;
	u64			reserved2;
} __attribute__ ((packed));

enum acpi_address_range_id {
	ACPI_ADDRESS_RANGE_MEMORY = 1,
	ACPI_ADDRESS_RANGE_RESERVED = 2,
	ACPI_ADDRESS_RANGE_ACPI = 3,
	ACPI_ADDRESS_RANGE_NVS	= 4,
	ACPI_ADDRESS_RANGE_COUNT
};

/*
 * System Locality Information Table (SLIT)
 *   see http://devresource.hp.com/devresource/docs/techpapers/ia64/slit.pdf
 */

struct acpi_table_slit {
	struct acpi_table_header header;
	u64			localities;
	u8			entry[1];	/* real size = localities^2 */
} __attribute__ ((packed));

/* Smart Battery Description Table (SBST) */

struct acpi_table_sbst {
	struct acpi_table_header header;
	u32			warning;	/* Warn user */
	u32			low;		/* Critical sleep */
	u32			critical;	/* Critical shutdown */
} __attribute__ ((packed));

/* Embedded Controller Boot Resources Table (ECDT) */

struct acpi_table_ecdt {
	struct acpi_table_header 	header;
	struct acpi_generic_address	ec_control;
	struct acpi_generic_address	ec_data;
	u32				uid;
	u8				gpe_bit;
	char				ec_id[0];
} __attribute__ ((packed));

/* PCI MMCONFIG */

/* Defined in PCI Firmware Specification 3.0 */
struct acpi_table_mcfg_config {
	u32				base_address;
	u32				base_reserved;
	u16				pci_segment_group_number;
	u8				start_bus_number;
	u8				end_bus_number;
	u8				reserved[4];
} __attribute__ ((packed));
struct acpi_table_mcfg {
	struct acpi_table_header	header;
	u8				reserved[8];
	struct acpi_table_mcfg_config	config[0];
} __attribute__ ((packed));

/* Table Handlers */

enum acpi_table_id {
	ACPI_TABLE_UNKNOWN = 0,
	ACPI_APIC,
	ACPI_BOOT,
	ACPI_DBGP,
	ACPI_DSDT,
	ACPI_ECDT,
	ACPI_ETDT,
	ACPI_FADT,
	ACPI_FACS,
	ACPI_OEMX,
	ACPI_PSDT,
	ACPI_SBST,
	ACPI_SLIT,
	ACPI_SPCR,
	ACPI_SRAT,
	ACPI_SSDT,
	ACPI_SPMI,
	ACPI_HPET,
	ACPI_MCFG,
	ACPI_TABLE_COUNT
};

typedef int (*acpi_table_handler) (unsigned long phys_addr, unsigned long size);

extern acpi_table_handler acpi_table_ops[ACPI_TABLE_COUNT];

typedef int (*acpi_madt_entry_handler) (acpi_table_entry_header *header, const unsigned long end);

static char * __acpi_map_table (unsigned long phys_addr, unsigned long size);
static void *acpi_find_rsdp (void);
int acpi_boot_init (void);
int acpi_boot_table_init (void);
int acpi_numa_init (void);

static int acpi_table_init (void);
int acpi_table_parse (enum acpi_table_id id, acpi_table_handler handler);
static int acpi_get_table_header_early (enum acpi_table_id id, struct acpi_table_header **header);
static int acpi_table_parse_madt (enum acpi_madt_entry_id id, acpi_madt_entry_handler handler, unsigned int max_entries);
int acpi_table_parse_srat (enum acpi_srat_entry_id id, acpi_madt_entry_handler handler, unsigned int max_entries);
int acpi_parse_mcfg (unsigned long phys_addr, unsigned long size);

/* from mpspec.h */
#define MAX_APICS 255

/* below here from drivers/acpi/tables.c */

#define PREFIX			"ACPI: "

#define ACPI_MAX_TABLES		128

static char *acpi_table_signatures[ACPI_TABLE_COUNT] = {
	[ACPI_TABLE_UNKNOWN] = "????",
	[ACPI_APIC] = "APIC",
	[ACPI_BOOT] = "BOOT",
	[ACPI_DBGP] = "DBGP",
	[ACPI_DSDT] = "DSDT",
	[ACPI_ECDT] = "ECDT",
	[ACPI_ETDT] = "ETDT",
	[ACPI_FADT] = "FACP",
	[ACPI_FACS] = "FACS",
	[ACPI_OEMX] = "OEM",
	[ACPI_PSDT] = "PSDT",
	[ACPI_SBST] = "SBST",
	[ACPI_SLIT] = "SLIT",
	[ACPI_SPCR] = "SPCR",
	[ACPI_SRAT] = "SRAT",
	[ACPI_SSDT] = "SSDT",
	[ACPI_SPMI] = "SPMI",
	[ACPI_HPET] = "HPET",
	[ACPI_MCFG] = "MCFG",
};

/* System Description Table (RSDT/XSDT) */
struct acpi_table_sdt {
	unsigned long pa;
	enum acpi_table_id id;
	unsigned long size;
} __attribute__ ((packed));

static unsigned long sdt_count;	/* Table count */

static struct acpi_table_xsdt *mapped_xsdt = NULL;
static struct acpi_table_rsdt *mapped_rsdt = NULL;

static struct acpi_table_sdt sdt_entry[ACPI_MAX_TABLES] __initdata;


/*
 * acpi_get_table_header_early()
 * for acpi_blacklisted(), acpi_table_get_sdt()
 */
static int __init
acpi_get_table_header_early(enum acpi_table_id id,
			    struct acpi_table_header **header)
{
	unsigned int i;
	enum acpi_table_id temp_id;

	/* DSDT is different from the rest */
	if (id == ACPI_DSDT)
		temp_id = ACPI_FADT;
	else
		temp_id = id;

	/* Locate the table. */

	for (i = 0; i < sdt_count; i++) {
		if (sdt_entry[i].id != temp_id)
			continue;
		*header = (void *)
		    __acpi_map_table(sdt_entry[i].pa, sdt_entry[i].size);
		if (!*header) {
			printk(KERN_WARNING PREFIX "Unable to map %s\n",
			       acpi_table_signatures[temp_id]);
			return -ENODEV;
		}
                printk("%d mapped header %lu at %p\n", __LINE__,
                        sdt_entry[i].size, (void *)sdt_entry[i].pa);
		break;
	}

	if (!*header) {
		printk(KERN_WARNING PREFIX "%s not present\n",
		       acpi_table_signatures[id]);
		return -ENODEV;
	}

	/* Map the DSDT header via the pointer in the FADT */
	if (id == ACPI_DSDT) {
		struct fadt_descriptor_rev2 *fadt =
		    (struct fadt_descriptor_rev2 *)*header;

		if (fadt->revision == 3 && fadt->Xdsdt) {
			*header = (void *)__acpi_map_table(fadt->Xdsdt,
							   sizeof(struct
								  acpi_table_header));
		} else if (fadt->V1_dsdt) {
			*header = (void *)__acpi_map_table(fadt->V1_dsdt,
							   sizeof(struct
								  acpi_table_header));
		} else
			*header = NULL;

		if (!*header) {
			printk(KERN_WARNING PREFIX "Unable to map DSDT\n");
			printk("%d freeing %p\n", __LINE__, fadt);
			free(fadt);
			return -ENODEV;
		}
		printk("%d freeing %p\n", __LINE__, fadt);
		free(fadt);
	}

	return 0;
}

static int __init
acpi_table_parse_madt_family(enum acpi_table_id id,
			     unsigned long madt_size,
			     int entry_id,
			     acpi_madt_entry_handler handler,
			     unsigned int max_entries)
{
	void *madt = NULL;
	acpi_table_entry_header *entry;
	unsigned int count = 0;
	unsigned long madt_end;
	unsigned int i;

	if (!handler)
		return -EINVAL;

	/* Locate the MADT (if exists). There should only be one. */

	for (i = 0; i < sdt_count; i++) {
		if (sdt_entry[i].id != id)
			continue;
		madt = (void *)
		    __acpi_map_table(sdt_entry[i].pa, sdt_entry[i].size);
		if (!madt) {
			printk(KERN_WARNING PREFIX "Unable to map %s\n",
			       acpi_table_signatures[id]);
			return -ENODEV;
		}
                printk("%d mapped header %lu at %p\n", __LINE__,
                        sdt_entry[i].size, (void *)sdt_entry[i].pa);
		break;
	}

	if (!madt) {
		printk(KERN_WARNING PREFIX "%s not present\n",
		       acpi_table_signatures[id]);
		return -ENODEV;
	}

	madt_end = (unsigned long)madt + sdt_entry[i].size;

	/* Parse all entries looking for a match. */

	entry = (acpi_table_entry_header *)
	    ((unsigned long)madt + madt_size);

	while (((unsigned long)entry) + sizeof(acpi_table_entry_header) <
	       madt_end) {
		if (entry->type == entry_id
		    && (!max_entries || count++ < max_entries))
			if (handler(entry, madt_end))
				return -EINVAL;

		entry = (acpi_table_entry_header *)
		    ((unsigned long)entry + entry->length);
	}
	if (max_entries && count > max_entries) {
		printk(KERN_WARNING PREFIX "[%s:0x%02x] ignored %i entries of "
		       "%i found\n", acpi_table_signatures[id], entry_id,
		       count - max_entries, count);
	}

	return count;
}

static int __init
acpi_table_parse_madt(enum acpi_madt_entry_id id,
		      acpi_madt_entry_handler handler, unsigned int max_entries)
{
	return acpi_table_parse_madt_family(ACPI_APIC,
					    sizeof(struct acpi_table_madt), id,
					    handler, max_entries);
}

static int
acpi_table_compute_checksum(void *table_pointer, unsigned long length)
{
	u8 *p = (u8 *) table_pointer;
	unsigned long remains = length;
	unsigned long sum = 0;

	if (!p || !length)
		return -EINVAL;

	while (remains--)
		sum += *p++;

	return (sum & 0xFF);
}


/* from arch/i386/kernel/acpi/boot.c */
static u64 acpi_lapic_addr __initdata = APIC_DEFAULT_PHYS_BASE;

#define MAX_MADT_ENTRIES	256
u8 x86_acpiid_to_apicid[MAX_MADT_ENTRIES] =
    {[0 ... MAX_MADT_ENTRIES - 1] = 0xff };

#define BAD_MADT_ENTRY(entry, end) (					    \
		(!entry) || (unsigned long)entry + sizeof(*entry) > end ||  \
		((acpi_table_entry_header *)entry)->length != sizeof(*entry))

static inline int acpi_madt_oem_check(char *oem_id, char *oem_table_id) {
    return 0;
}

static void acpi_table_print(struct acpi_table_header *header, unsigned long phys_addr)
{
	char *name = NULL;

	if (!header)
		return;

	/* Some table signatures aren't good table names */

	if (!strncmp((char *)&header->signature,
		     acpi_table_signatures[ACPI_APIC],
		     sizeof(header->signature))) {
		name = "MADT";
	} else if (!strncmp((char *)&header->signature,
			    acpi_table_signatures[ACPI_FADT],
			    sizeof(header->signature))) {
		name = "FADT";
	} else
		name = header->signature;

	printk(KERN_DEBUG PREFIX
	       "%.4s (v%3.3d %6.6s %8.8s 0x%08x %.4s 0x%08x) @ 0x%p\n", name,
	       header->revision, header->oem_id, header->oem_table_id,
	       header->oem_revision, header->asl_compiler_id,
	       header->asl_compiler_revision, (void *)phys_addr);
}

#if 0
static int __init acpi_parse_madt(unsigned long phys_addr, unsigned long size)
{
	struct acpi_table_madt *madt = NULL;

	if (!phys_addr || !size)
		return -EINVAL;

	madt = (struct acpi_table_madt *)__acpi_map_table(phys_addr, size);
	if (!madt) {
		printk(KERN_WARNING PREFIX "Unable to map MADT\n");
		return -ENODEV;
	}

	if (madt->lapic_address) {
		acpi_lapic_addr = (u64) madt->lapic_address;

		printk(KERN_DEBUG PREFIX "Local APIC address 0x%08x\n",
		       madt->lapic_address);
	}

	acpi_madt_oem_check(madt->header.oem_id, madt->header.oem_table_id);

	return 0;
}
#endif

static int __init
acpi_parse_lapic(acpi_table_entry_header * header, const unsigned long end)
{
	struct acpi_table_lapic *processor = NULL;

	processor = (struct acpi_table_lapic *)header;

	if (BAD_MADT_ENTRY(processor, end))
		return -EINVAL;

	/* Record local apic id only when enabled */
	if (processor->flags.enabled)
		x86_acpiid_to_apicid[processor->acpi_id] = processor->id;

	/*
	 * We need to register disabled CPU as well to permit
	 * counting disabled CPUs. This allows us to size
	 * cpus_possible_map more accurately, to permit
	 * to not preallocating memory for all NR_CPUS
	 * when we use CPU hotplug.
	 */
	mp_register_lapic(processor->id,	/* APIC ID */
			  processor->flags.enabled);	/* Enabled? */

	return 0;
}

static int __init
acpi_parse_lapic_addr_ovr(acpi_table_entry_header * header,
			  const unsigned long end)
{
	struct acpi_table_lapic_addr_ovr *lapic_addr_ovr = NULL;

	lapic_addr_ovr = (struct acpi_table_lapic_addr_ovr *)header;

	if (BAD_MADT_ENTRY(lapic_addr_ovr, end))
		return -EINVAL;

	acpi_lapic_addr = lapic_addr_ovr->address;

	return 0;
}

static int __init
acpi_parse_lapic_nmi(acpi_table_entry_header * header, const unsigned long end)
{
	struct acpi_table_lapic_nmi *lapic_nmi = NULL;

	lapic_nmi = (struct acpi_table_lapic_nmi *)header;

	if (BAD_MADT_ENTRY(lapic_nmi, end))
		return -EINVAL;

	if (lapic_nmi->lint != 1)
		printk(KERN_WARNING PREFIX "NMI not connected to LINT 1!\n");

	return 0;
}

static void *__init
acpi_scan_rsdp(unsigned long start, unsigned long length)
{
	unsigned long offset = 0;
	unsigned long sig_len = sizeof("RSD PTR ") - 1;
	char *ptr;

	/*
	 * Scan all 16-byte boundaries of the physical memory region for the
	 * RSDP signature.
	 */
	ptr = mem_chunk(0, 0x100000, "/dev/mem");
	if (!ptr)
	    return 0;

	for (offset = 0; offset < length; offset += 16) {
		if (strncmp(ptr+start+offset, "RSD PTR ", sig_len))
			continue;
		free(ptr);
		return (void *)start + offset;
	}
	free(ptr);

	return 0;
}

static void * __init acpi_find_rsdp(void)
{
	void *rsdp_phys = 0;

	if (efi_enabled) {
		if (efi.acpi20)
			return __pa(efi.acpi20);
		else if (efi.acpi)
			return __pa(efi.acpi);
	}
	/*
	 * Scan memory looking for the RSDP signature. First search EBDA (low
	 * memory) paragraphs and then search upper memory (E0000-FFFFF).
	 */
	rsdp_phys = acpi_scan_rsdp(0, 0x400);
	if (!rsdp_phys)
		rsdp_phys = acpi_scan_rsdp(0xE0000, 0x20000);

	return rsdp_phys;
}

static int __init acpi_parse_madt_lapic_entries(void)
{
	int count;

	/* 
	 * Note that the LAPIC address is obtained from the MADT (32-bit value)
	 * and (optionally) overriden by a LAPIC_ADDR_OVR entry (64-bit value).
	 */

	count =
	    acpi_table_parse_madt(ACPI_MADT_LAPIC_ADDR_OVR,
				  acpi_parse_lapic_addr_ovr, 0);
	if (count < 0) {
		printk(KERN_ERR PREFIX
		       "Error parsing LAPIC address override entry\n");
		return count;
	}

#if 0
	mp_register_lapic_address(acpi_lapic_addr);
#endif

	count = acpi_table_parse_madt(ACPI_MADT_LAPIC, acpi_parse_lapic,
				      MAX_APICS);
	if (!count) {
		printk(KERN_ERR PREFIX "No LAPIC entries present\n");
		/* TBD: Cleanup to allow fallback to MPS */
		return -ENODEV;
	} else if (count < 0) {
		printk(KERN_ERR PREFIX "Error parsing LAPIC entry\n");
		/* TBD: Cleanup to allow fallback to MPS */
		return count;
	}

	count =
	    acpi_table_parse_madt(ACPI_MADT_LAPIC_NMI, acpi_parse_lapic_nmi, 0);
	if (count < 0) {
		printk(KERN_ERR PREFIX "Error parsing LAPIC NMI entry\n");
		/* TBD: Cleanup to allow fallback to MPS */
		return count;
	}
	return 0;
}

static int __init acpi_table_get_sdt(struct acpi_table_rsdp *rsdp)
{
	struct acpi_table_header *header = NULL;
	unsigned int i, id = 0;
        unsigned long sdt_pa;	/* Physical Address */

	if (!rsdp)
		return -EINVAL;

	/* First check XSDT (but only on ACPI 2.0-compatible systems) */

	if ((rsdp->revision >= 2) &&
	    (((struct acpi20_table_rsdp *)rsdp)->xsdt_address)) {

		struct acpi_table_xsdt *mapped_xsdt = NULL;

		sdt_pa = ((struct acpi20_table_rsdp *)rsdp)->xsdt_address;

		/* map in just the header */
		header = (struct acpi_table_header *)
		    __acpi_map_table(sdt_pa, sizeof(struct acpi_table_header));

		if (!header) {
			printk(KERN_WARNING PREFIX
			       "Unable to map XSDT header\n");
                        free(header);
			return -ENODEV;
		}

		/* remap in the entire table before processing */
                printk("%d length: %u\n", __LINE__, header->length);
		mapped_xsdt = (struct acpi_table_xsdt *)
		    __acpi_map_table(sdt_pa, header->length);
                free(header);
		if (!mapped_xsdt) {
			printk(KERN_WARNING PREFIX "Unable to map XSDT\n");
                        free(mapped_xsdt);
                        mapped_xsdt = NULL;
			return -ENODEV;
		}
		header = &mapped_xsdt->header;

		if (strncmp(header->signature, "XSDT", 4)) {
			printk(KERN_WARNING PREFIX
			       "XSDT signature incorrect\n");
                        free(header);
                        free(mapped_xsdt);
                        mapped_xsdt = NULL;
			return -ENODEV;
		}

		if (acpi_table_compute_checksum(header, header->length)) {
			printk(KERN_WARNING PREFIX "Invalid XSDT checksum\n");
                        free(header);
                        free(mapped_xsdt);
                        mapped_xsdt = NULL;
			return -ENODEV;
		}

		sdt_count =
		    (header->length - sizeof(struct acpi_table_header)) >> 3;
		if (sdt_count > ACPI_MAX_TABLES) {
			printk(KERN_WARNING PREFIX
			       "Truncated %lu XSDT entries\n",
			       (sdt_count - ACPI_MAX_TABLES));
			sdt_count = ACPI_MAX_TABLES;
		}

		for (i = 0; i < sdt_count; i++)
			sdt_entry[i].pa = (unsigned long)mapped_xsdt->entry[i];
                free(header);
	}

	/* Then check RSDT */

	else if (rsdp->rsdt_address) {

		sdt_pa = rsdp->rsdt_address;

		/* map in just the header */
		header = (struct acpi_table_header *)
		    __acpi_map_table(sdt_pa, sizeof(struct acpi_table_header));
		if (!header) {
			printk(KERN_WARNING PREFIX
			       "Unable to map RSDT header\n");
                        free(header);
			return -ENODEV;
		}

		/* remap in the entire table before processing */
		mapped_rsdt = (struct acpi_table_rsdt *)
		    __acpi_map_table((unsigned long)sdt_pa, header->length);
                free(header);
		if (!mapped_rsdt) {
			printk(KERN_WARNING PREFIX "Unable to map RSDT\n");
                        free(mapped_rsdt);
                        mapped_rsdt = NULL;
			return -ENODEV;
		}
		header = &mapped_rsdt->header;

		if (strncmp(header->signature, "RSDT", 4)) {
			printk(KERN_WARNING PREFIX
			       "RSDT signature incorrect\n");
                        free(header);
                        free(mapped_rsdt);
                        mapped_rsdt = NULL;
			return -ENODEV;
		}

		if (acpi_table_compute_checksum(header, header->length)) {
			printk(KERN_WARNING PREFIX "Invalid RSDT checksum\n");
                        free(header);
                        free(mapped_rsdt);
                        mapped_rsdt = NULL;
			return -ENODEV;
		}

		sdt_count =
		    (header->length - sizeof(struct acpi_table_header)) >> 2;
		if (sdt_count > ACPI_MAX_TABLES) {
			printk(KERN_WARNING PREFIX
			       "Truncated %lu RSDT entries\n",
			       (sdt_count - ACPI_MAX_TABLES));
			sdt_count = ACPI_MAX_TABLES;
		}

		for (i = 0; i < sdt_count; i++)
			sdt_entry[i].pa = (unsigned long)mapped_rsdt->entry[i];
                free(header);
	}

	else {
		printk(KERN_WARNING PREFIX
		       "No System Description Table (RSDT/XSDT) specified in RSDP\n");
		return -ENODEV;
	}

	acpi_table_print(header, sdt_pa);

	for (i = 0; i < sdt_count; i++) {
                struct acpi_table_header *h1;

                if (sdt_entry[i].pa == 0 && sdt_entry[i].id == ACPI_TABLE_UNKNOWN)
                    continue;
		/* map in just the header */
		header = (struct acpi_table_header *)
		    __acpi_map_table(sdt_entry[i].pa,
				     sizeof(struct acpi_table_header));
		if (!header)
			continue;

		/* remap in the entire table before processing */
                h1 = header;
		header = (struct acpi_table_header *)
		    __acpi_map_table(sdt_entry[i].pa, header->length);
                free(h1);
		if (!header)
			continue;

		acpi_table_print(header, sdt_entry[i].pa);

		if (acpi_table_compute_checksum(header, header->length)) {
			printk(KERN_WARNING "  >>> ERROR: Invalid checksum\n");
			continue;
		}

		sdt_entry[i].size = header->length;

		for (id = 0; id < ACPI_TABLE_COUNT; id++) {
			if (!strncmp((char *)&header->signature,
				     acpi_table_signatures[id],
				     sizeof(header->signature))) {
				sdt_entry[i].id = id;
			}
		}
	}

	/* 
	 * The DSDT is *not* in the RSDT (why not? no idea.) but we want
	 * to print its info, because this is what people usually blacklist
	 * against. Unfortunately, we don't know the phys_addr, so just
	 * print 0. Maybe no one will notice.
	 */
	if (!acpi_get_table_header_early(ACPI_DSDT, &header))
		acpi_table_print(header, 0);

        printk("%d freeing %p\n", __LINE__, header);
        free(header);
	return 0;
}

/*
 * acpi_table_init()
 *
 * find RSDP, find and checksum SDT/XSDT.
 * checksum all tables, print SDT/XSDT
 * 
 * result: sdt_entry[] is initialized
 */

static int acpi_table_init(void)
{
	void *rsdp_phys = 0;
	int result = 0;

	/* Locate and map the Root System Description Table (RSDP) */

	rsdp_phys = acpi_find_rsdp();
	if (!rsdp_phys) {
		printk(KERN_ERR PREFIX "Unable to locate RSDP\n");
		return -ENODEV;
	}

	rsdp = mem_chunk((unsigned long)rsdp_phys, sizeof (*rsdp), "/dev/mem");
	if (!rsdp) {
		printk(KERN_WARNING PREFIX "Unable to map RSDP\n");
		return -ENODEV;
	}

	printk(KERN_DEBUG PREFIX
	       "RSDP (v%3.3d %6.6s                                ) @ 0x%p\n",
	       rsdp->revision, rsdp->oem_id, (void *)rsdp_phys);

	if (rsdp->revision < 2)
		result =
		    acpi_table_compute_checksum(rsdp,
						sizeof(struct acpi_table_rsdp));
	else
		result =
		    acpi_table_compute_checksum(rsdp,
						((struct acpi20_table_rsdp *)
						 rsdp)->length);

	if (result) {
		printk(KERN_WARNING "  >>> ERROR: Invalid checksum\n");
		printk("%d freeing %p\n", __LINE__, rsdp);
                free(rsdp);
                rsdp = NULL;
		return -ENODEV;
	}

	/* Locate and map the System Description table (RSDT/XSDT) */

	result = acpi_table_get_sdt(rsdp);
	if (result) {
	    printk("%d freeing %p\n", __LINE__, rsdp);
            free(rsdp);
            rsdp = NULL;
            return -ENODEV;
        }

	return 0;
}

/* original code */

/* not actually from arch/i386/kernel/acpi/boot.c... */
static char *__acpi_map_table(unsigned long phys, unsigned long size)
{
    char *ret = mem_chunk(phys, size, "/dev/mem");

    return ret;
}

static int ncpus=0;

static void mp_register_lapic(u8 id, u8 enabled)
{
#ifdef ANACONDA_COUNT_MISSING_HOTPLUGGABLE_CPUS
    ncpus++;
#else
    if (enabled)
        ncpus++;
#endif
}

int detectAcpiCpusAvailable(void)
{
    int result;
    ncpus = 0;

    result = acpi_table_init();
    if (result < 0) {
        return 0;
    }
    acpi_parse_madt_lapic_entries();
    if (mapped_xsdt) {
	printk("%d freeing %p\n", __LINE__, mapped_xsdt);
        free(mapped_xsdt);
    }
    if (mapped_rsdt) {
	printk("%d freeing %p\n", __LINE__, mapped_rsdt);
        free(mapped_rsdt);
    }
    printk("%d freeing %p\n", __LINE__, rsdp);
    free(rsdp);

    return ncpus;
}
#else /* !defined(__i386__) && !defined(__x86_64__) */

int detectAcpiCpusAvailable(void)
{
    return 0;
}

#endif
