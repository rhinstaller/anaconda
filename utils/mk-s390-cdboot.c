/*
 * mk-s390-cdboot -- creates one big image using a kernel, a ramdisk and
 *                     a parmfile
 *
 *
 * 2003-07-24 Volker Sameske <sameske@de.ibm.com>
 *
 * compile with:
 *     gcc -Wall -o mk-s390-cdboot mk-s390-cdboot.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <getopt.h>
#include <string.h>
#include <stdarg.h>

#define BUFFER_LEN 1024
#define INITRD_START 0x0000000000800000LL
#define START_PSW_ADDRESS 0x80010000
#define PARAMETER_BUFFER_LEN 80

static struct option getopt_long_options[]=
{
        { "image",       1, 0, 'i'},
        { "ramdisk",     1, 0, 'r'},
        { "parmfile",    1, 0, 'p'},
        { "outfile",     1, 0, 'o'},
        { "help",        0, 0, 'h'},
        {0, 0, 0, 0}
};


static void usage(char *cmd)
{
        printf("%s [-h] [-v] -i <kernel> -r <ramdisk> -p <parmfile> -o <outfile>\n", cmd);
}


int main (int argc, char **argv)
{
	char *cmd = basename(argv[0]);
	FILE *fd1;
	FILE *fd2;
	FILE *fd3;
	FILE *fd4;
	char buffer[BUFFER_LEN];
	int rc, oc, index;
	unsigned long long initrd_start = INITRD_START;
	unsigned long long initrd_size;
	char image[PARAMETER_BUFFER_LEN];
	char ramdisk[PARAMETER_BUFFER_LEN];
	char parmfile[PARAMETER_BUFFER_LEN];
	char outfile[PARAMETER_BUFFER_LEN];
	int image_specified    = 0;
	int ramdisk_specified  = 0;
	int parmfile_specified = 0;
	int outfile_specified  = 0;
	int start_psw_address  = START_PSW_ADDRESS;

        opterr=0;
        while (1)
        {
                oc = getopt_long(argc, argv, "i:r:p:o:h?", getopt_long_options, &index);
                if (oc==-1) break;

                switch (oc)
                {
                case '?':
                case 'h':
                        usage(cmd);
                        exit(0);
                case 'i':
			strcpy(image, optarg);
                        image_specified = 1;
                        break;
		case 'r':
                        strcpy(ramdisk, optarg);
                        ramdisk_specified = 1;
                        break;
		case 'p':
                        strcpy(parmfile, optarg);
                        parmfile_specified = 1;
                        break;
		case 'o':
                        strcpy(outfile, optarg);
                        outfile_specified = 1;
                        break;
		default:
                        usage(cmd);
                        exit(0);
                }
        }

	if (!image_specified || !ramdisk_specified ||
	    !parmfile_specified || !outfile_specified) {
		usage(cmd);
		exit(0);
	}

	printf("Creating bootable CD-ROM image...\n");
        printf("kernel is  : %s\n", image);
        printf("ramdisk is : %s\n", ramdisk);
        printf("parmfile is: %s\n", parmfile);
        printf("outfile is : %s\n", outfile);

	fd1 = fopen(outfile, "w");
	fd2 = fopen(image, "r");
	fd3 = fopen(ramdisk, "r");
	fd4 = fopen(parmfile, "r");

	printf("writing kernel...\n");
	while (1) {
		rc = fread(buffer, BUFFER_LEN, 1, fd2);
		fwrite(buffer, BUFFER_LEN, 1, fd1);
		if (rc == 0) break;
	}

	printf("writing initrd...\n");
	fseek(fd1, initrd_start, SEEK_SET);
	while (1) {
		rc = fread(buffer, BUFFER_LEN, 1, fd3);
		fwrite(buffer, BUFFER_LEN, 1, fd1);
		if (rc == 0) break;
	}

	fseek(fd3, 0 ,SEEK_END);
	initrd_size = ftell(fd3);

	printf("changing start PSW address to 0x%08x...\n", start_psw_address);
	fseek(fd1, 0x4, SEEK_SET);
	fwrite(&start_psw_address, 4, 1, fd1);

	printf("writing initrd address and size...\n");
	printf("INITRD start: 0x%016llx\n",  initrd_start);
	printf("INITRD size : 0x%016llx\n", initrd_size);

	fseek(fd1, 0x10408, SEEK_SET);
	fwrite(&initrd_start, 8, 1, fd1);
	fseek(fd1, 0x10410, SEEK_SET);
	fwrite(&initrd_size, 8, 1, fd1);

	printf("writing parmfile...\n");
	fseek(fd1, 0x10480, SEEK_SET);
	while (1) {
		rc = fread(buffer, 1, 1, fd4);
		fwrite(buffer, 1, 1, fd1);
		if (rc == 0) break;
	}

	fclose(fd1);
	fclose(fd2);
	fclose(fd3);
	fclose(fd4);
	return 0;
}
