/* Sun style partitioning */

#include <fcntl.h>
#include <unistd.h>

#include "balkan.h"

#define BSD_DISKMAGIC	(0x82564557UL)	/* The disk magic number */
#define BSD_MAXPARTITIONS	8
#define BSD_FS_UNUSED		0	/* disklabel unused partition entry ID */
#define BSD_LABEL_OFFSET	64

struct bsd_disklabel {
    unsigned int	d_magic;		/* the magic number */
    signed short	d_type;			/* drive type */
    signed short	d_subtype;		/* controller/d_type specific */
    char	d_typename[16];		/* type name, e.g. "eagle" */
    char	d_packname[16];			/* pack identifier */ 
    unsigned int	d_secsize;		/* # of bytes per sector */
    unsigned int	d_nsectors;		/* # of data sectors per track */
    unsigned int	d_ntracks;		/* # of tracks per cylinder */
    unsigned int	d_ncylinders;		/* # of data cylinders per unit */
    unsigned int	d_secpercyl;		/* # of data sectors per cylinder */
    unsigned int	d_secperunit;		/* # of data sectors per unit */
    unsigned short	d_sparespertrack;	/* # of spare sectors per track */
    unsigned short	d_sparespercyl;		/* # of spare sectors per cylinder */
    unsigned int	d_acylinders;		/* # of alt. cylinders per unit */
    unsigned short	d_rpm;			/* rotational speed */
    unsigned short	d_interleave;		/* hardware sector interleave */
    unsigned short	d_trackskew;		/* sector 0 skew, per track */
    unsigned short	d_cylskew;		/* sector 0 skew, per cylinder */
    unsigned int	d_headswitch;		/* head switch time, usec */
    unsigned int	d_trkseek;		/* track-to-track seek, usec */
    unsigned int	d_flags;		/* generic flags */
    #define NDDATA 5
    unsigned int	d_drivedata[NDDATA];	/* drive-type specific information */
    #define NSPARE 5
    unsigned int	d_spare[NSPARE];	/* reserved for future use */
    unsigned int	d_magic2;		/* the magic number (again) */
    unsigned short	d_checksum;		/* xor of data incl. partitions */

		    /* filesystem and partition information: */
    unsigned short	d_npartitions;		/* number of partitions in following */
    unsigned int	d_bbsize;		/* size of boot area at sn0, bytes */
    unsigned int	d_sbsize;		/* max size of fs superblock, bytes */
    struct	bsd_partition {		/* the partition table */
	    unsigned int	p_size;		/* number of sectors in partition */
	    unsigned int	p_offset;	/* starting sector */
	    unsigned int	p_fsize;	/* filesystem basic fragment size */
	    unsigned char	p_fstype;	/* filesystem type, see below */
	    unsigned char	p_frag;		/* filesystem fragments per block */
	    unsigned short	p_cpg;		/* filesystem cylinders per group */
    } d_partitions[BSD_MAXPARTITIONS];	/* actually may be more */
};

long long llseek(int fd, long long offset, int whence);

#if 0
static unsigned short xbsd_dkcksum (struct bsd_disklabel *lp) {
  unsigned short *start, *end;
  unsigned short sum = 0;
  
  lp->d_checksum = 0;
  start = (u_short *)lp;
  end = (u_short *)&lp->d_partitions[lp->d_npartitions];
  while (start < end)
    sum ^= *start++;
  return (sum);
}
#endif

int bsdlReadTable(int fd, struct partitionTable * table) {
    struct bsd_disklabel label;
    int i, rc;
    unsigned short *p, csum;
    int s;

    table->maxNumPartitions = 8;

    for (i = 0; i < table->maxNumPartitions; i++)
	table->parts[i].type = -1;

    table->sectorSize = 512;

    if (lseek(fd, BSD_LABEL_OFFSET, SEEK_SET) < 0)
	return BALKAN_ERROR_ERRNO;

    if (read(fd, &label, sizeof(label)) != sizeof(label))
	return BALKAN_ERROR_ERRNO;

    if (label.d_magic != BSD_DISKMAGIC) 
	return BALKAN_ERROR_BADMAGIC;

#if 0
    /* minlabel doens't write checksums :-( */
    if (xbsd_dkcksum(&label))
	return BALKAN_ERROR_BADMAGIC;
#endif

    if (label.d_npartitions > 8)
	label.d_npartitions = 8;

    for (i = 0; i < label.d_npartitions; i++) {
	if (label.d_partitions[i].p_size && label.d_partitions[i].p_fstype) {
	    table->parts[i].startSector = label.d_partitions[i].p_offset;
	    table->parts[i].size = label.d_partitions[i].p_size;

	    switch (label.d_partitions[i].p_fstype) {
	      case 1: s = BALKAN_PART_SWAP; break;
	      case 8: s = BALKAN_PART_EXT2; break;
	      default: s = BALKAN_PART_OTHER; break;
	    }
	    table->parts[i].type = s;
	}
    }

    return 0;
}

#ifdef STANDALONE_TEST

void main() {
    int fd;
    int i;
    struct partitionTable table;

    fd = open("/dev/hda", O_RDONLY);

    printf("rc= %d\n", bsdlReadTable(fd, &table));

    for (i = 0; i < table.maxNumPartitions; i++) {
	if (table.parts[i].type == -1) continue;

	printf("%d: %x %d\n", i, table.parts[i].type, table.parts[i].size);
    }
}

#endif
