#include <sys/types.h>
#include <sys/io.h>
#include <sys/stat.h>
#include <sys/vm86.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <netinet/in.h>
#include "vbe.h"
#include "vesamode.h"
#include "bioscall.h"
#ident "$Id$"

int main(int argc, char **argv)
{
	struct vm86_struct info;
	struct vbe_info *vbe_info = NULL;
	struct edid_info *edid_info = NULL;
	unsigned char *memory = NULL;
	u_int16_t *mode_list = NULL;
	char manufacturer[4];
	int i;

	/* Get a copy of the low megabyte for use as an address space. */
	memory = vm86_ram_alloc();
	if(memory == MAP_FAILED) {
		printf("Couldn't allocate needed memory!\n");
		exit(0);
	}

	/* Set up registers for a real-mode interrupt call. */
	memset(&info, 0, sizeof(info));
	info.regs.eax = 0x4f00;
	info.regs.es  = 0x4000;
	info.regs.edi = 0x0000;
	info.regs.ss  = 0x9000;
	info.regs.esp = 0x0000;
	info.flags    = 0;

	/* Call the BIOS. */
	memset(&memory[info.regs.es * 16 + info.regs.edi], 0, 1024);
	bioscall(0x10, &info.regs, memory);

	/* Interpret results. */
	vbe_info = (struct vbe_info*) &memory[info.regs.es*16 + info.regs.edi];

	if((info.regs.eax & 0xff) != 0x4f) {
		printf("VESA BIOS Extensions not detected.\n");
		vm86_ram_free(memory);
		exit(0);
	}

	if((info.regs.eax & 0xffff) != 0x004f) {
		printf("VESA Get SuperVGA Information request failed.\n");
		vm86_ram_free(memory);
		exit(0);
	}

	/* Signature. */
	printf("%c%c%c%c %d.%d detected.\n",
	       vbe_info->signature[0], vbe_info->signature[1],
	       vbe_info->signature[2], vbe_info->signature[3],
	       vbe_info->version[1], vbe_info->version[0]);

	/* OEM */
	printf("OEM Name: %s\n", &memory[vbe_info->oem_name.addr.seg * 16 +
					 vbe_info->oem_name.addr.ofs]);

	/* Memory. */
	printf("Memory installed = %d * 64k blocks = %dkb\n",
	       vbe_info->memory_size, vbe_info->memory_size * 64);

	/* List supported standard modes. */
	mode_list = (u_int16_t*) &memory[vbe_info->mode_list.addr.seg * 16 +
					 vbe_info->mode_list.addr.ofs];
	if(*mode_list != 0xffff) {
		printf("Supported standard modes:\n");
	}
	for(;*mode_list != 0xffff; mode_list++) {
		int i;
		for(i = 0; known_vesa_modes[i].x != 0; i++) {
			if(known_vesa_modes[i].number == *mode_list) {
				printf("\t%s\n", known_vesa_modes[i].text);
			}
		}
	}

	/* Set up registers for reading the EDID from the BIOS. */
	memset(&info, 0, sizeof(info));
	info.regs.eax = 0x4f15;
	info.regs.ebx = 0x0001;
	info.regs.es  = 0x4000;
	info.regs.edi = 0x0000;
	info.regs.ss  = 0x9000;
	info.regs.esp = 0x0000;
	info.flags    = 0;

	/* Call the BIOS again. */
	memset(&memory[info.regs.es * 16 + info.regs.edi], 0, 1024);
	bioscall(0x10, &info.regs, memory);

	/* Interpret results. */
	if((info.regs.eax & 0xff) != 0x4f) {
		printf("EDID read not supported by hardware.\n");
		vm86_ram_free(memory);
		exit(0);
	}

	if((info.regs.eax & 0xffff) == 0x014f) {
		printf("EDID read supported by hardware, but failed "
		       "(monitor not DCC-capable?).\n");
#if 1
		vm86_ram_free(memory);
		exit(0);
#endif
	}

	if((info.regs.eax & 0xffff) != 0x004f) {
		printf("Unknown failure reading EDID.\n");
		dump_regs(&info.regs);
	} else {
		printf("EDID read successfully.\n");
		dump_regs(&info.regs);
	}

	edid_info = (struct edid_info*) &memory[info.regs.es * 16 +
						info.regs.edi];
	printf("EDID ver. %d rev. %d.\n",
	       edid_info->edid_version, edid_info->edid_revision);

	edid_info->manufacturer = ntohs(edid_info->manufacturer);
	manufacturer[0] = ((edid_info->manufacturer>>10)&0x1f)+ 'A' - 1;
	manufacturer[1] = ((edid_info->manufacturer>> 5)&0x1f)+ 'A' - 1;
	manufacturer[2] = ((edid_info->manufacturer>> 0)&0x1f)+ 'A' - 1;
	manufacturer[3] = 0;
	printf("Manufacturer: %s\n", manufacturer);

	if(edid_info->serial != 0xffffffff) {
		if(strcmp(manufacturer, "MAG") == 0) {
			edid_info->serial -= 0x7000000;
		}
		if(strcmp(manufacturer, "OQI") == 0) {
			edid_info->serial -= 456150000;
		}
		if(strcmp(manufacturer, "VSC") == 0) {
			edid_info->serial -= 640000000;
		}
	}
	printf("Serial number: %d.\n", edid_info->serial);

	printf("Manufactured in week %d of %d.\n",
	       edid_info->week, edid_info->year + 1990);

	printf("Input signal type: %s%s%s%s.\n",
	       edid_info->video_input & 0x01 ? "separate sync, " : "",
	       edid_info->video_input & 0x02 ? "composite sync, " : "",
	       edid_info->video_input & 0x04 ? "sync on green, " : "",
	       edid_info->video_input & 0x80 ?
	       "digital signal" : "analog signal");

	printf("Screen size max %d cm horizontal, %d cm vertical.\n",
	       edid_info->max_size_horizontal,
	       edid_info->max_size_vertical);

	printf("Gamma: %f.\n", edid_info->gamma / 100.0 + 1);

	printf("DPMS flags: %s, %s%s, %s%s, %s%s.\n",
	       edid_info->dpms_flags & 0x08 ? "RGB" : "non-RGB",
	       edid_info->dpms_flags & 0x20 ? "" : "no ", "active off",
	       edid_info->dpms_flags & 0x40 ? "" : "no ", "suspend",
	       edid_info->dpms_flags & 0x80 ? "" : "no ", "standby");

	printf("Established timings:\n");
	if(edid_info->established_timings1 & 0x01)
		printf("\t720x400 @ 70 Hz (VGA 640x400, IBM)\n");
	if(edid_info->established_timings1 & 0x02)
		printf("\t720x400 @ 88 Hz (XGA2)\n");
	if(edid_info->established_timings1 & 0x04)
		printf("\t640x480 @ 60 Hz (VGA)\n");
	if(edid_info->established_timings1 & 0x08)
		printf("\t640x480 @ 67 Hz (Mac II, Apple)\n");
	if(edid_info->established_timings1 & 0x10)
		printf("\t640x480 @ 72 Hz (VESA)\n");
	if(edid_info->established_timings1 & 0x20)
		printf("\t640x480 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings1 & 0x40)
		printf("\t800x600 @ 56 Hz (VESA)\n");
	if(edid_info->established_timings1 & 0x80)
		printf("\t800x600 @ 60 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x01)
		printf("\t800x600 @ 72 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x02)
		printf("\t800x600 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x04)
		printf("\t832x624 @ 75 Hz (Mac II)\n");
	if(edid_info->established_timings2 & 0x08)
		printf("\t1024x768 @ 87 Hz Interlaced (8514A)\n");
	if(edid_info->established_timings2 & 0x10)
		printf("\t1024x768 @ 60 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x20)
		printf("\t1024x768 @ 70 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x40)
		printf("\t1024x768 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings2 & 0x80)
		printf("\t1280x1024 @ 75 Hz (VESA)\n");

	/* Standard timings. */
	for(i = 0; i < 8; i++) {
		double aspect = 1;
		unsigned int x, y;
		unsigned char xres, vfreq;
		xres = edid_info->standard_timing[i].xresolution;
		vfreq = edid_info->standard_timing[i].vfreq;
		if((xres != vfreq) ||
		   ((xres != 0) && (xres != 1)) ||
		   ((vfreq != 0) && (vfreq != 1))) {
			switch(vfreq >> 6) {
				case 0: aspect = 1; break; /*undefined*/
				case 1: aspect = 0.750; break;
				case 2: aspect = 0.800; break;
				case 3: aspect = 0.625; break;
			}
			x = (xres + 31) * 8;
			y = x * aspect;
			printf("Standard timing %d: %d Hz, %dx%d\n", i,
			       (vfreq & 0x3f) + 60, x, y);
		}
	}

	/* Detailed timing information. */
	for(i = 0; i < 4; i++) {
		unsigned char *timing = NULL;
		timing = edid_info->detailed_timing[i];
		if((timing[0] != 0) || (timing[1] != 0) || (timing[0] != 0)) {
			printf("Detailed timing %d:\n", i);
			printf("\tHoriz. Sync = %d kHz\n", timing[0]);
			printf("\tVert. Freq. = %d Hz\n", timing[1]);
			printf("\tHoriz. Active Time = %d pixels\n",
			       timing[2]);
			printf("\tHoriz. Blank Interval = %d pixels\n",
			       timing[3]);
			printf("\tHoriz. Active Time 2 / Blanking "
			       "Interval 2 = %d\n", timing[4]);
			printf("\tVert. Active Time = %d lines\n",
			       timing[5]);
			printf("\tVert. Blanking Interval = %d lines\n",
			       timing[6]);
			printf("\tVert. Active Time 2 / Blanking "
			       "Interval 2 = %d\n", timing[7]);
			printf("\tHoriz. Sync Offset = %d pixels\n",
			       timing[8]);
			printf("\tHoriz. Sync Pulsewidth = %d pixels\n",
			       timing[9]);
			printf("\tVert. Sync Offset / Pulsewidth = %d\n",
			       timing[10]);
			printf("\tVert. Sync Offset 2 / Pulsewidth 2 = %d\n",
			       timing[11]);
			printf("\tImage Size = %dx%d mm\n",
			       timing[12], timing[13]);
			printf("\tHoriz. / Vert. Image Size 2 = %d mm\n",
			       timing[14]);
			printf("\tHoriz. Border Width = %d pixels\n",
			       timing[15]);
			printf("\tVert. Border Height = %d pixels\n",
			       timing[16]);
			printf("\tDisplay type: ");
			if(timing[17] & 0x80) printf("interlaced, ");
			switch((timing[17] >> 5) & 0x03) {
				case 0: {
					printf("non-stereo, ");
					break;
				}
				case 1: {
					printf("stereo, right stereo "
					       "sync high, ");
					break;
				}
				case 2: {
					printf("stereo, left stereo "
					       "sync high, ");
					break;
				}
				case 0x60: {
					printf("undefined stereo, ");
					break;
				}
			}
			switch((timing[17] >> 3) & 0x03) {
				case 0: {
					printf("sync analog composite");
					break;
				}
				case 1: {
					printf("sync bipolar analog "
					       "composite");
					break;
				}
				case 2: {
					printf("sync digital "
					       "composite");
					break;
				}
				case 3: {
					printf("sync digital separate");
					break;
				}
			}
			printf(".\n");
		} else {
			printf("Text info block %d: ", i);
			switch(timing[3]) {
				case 0xff: {
					printf("serial number: ");
					break;
				}
				case 0xfe: {
					printf("vendor name: ");
					break;
				}
				case 0xfd: {
					printf("frequency range: ");
					break;
				}
				case 0xfc: {
					printf("model name: ");
					break;
				}
			}
			if(timing[3] != 0xfd) {
				int j;
				for(j = 4; j < 18; j++) {
					if(isprint(timing[j])) {
						printf("%c", timing[j]);
					}
				}
			} else {
				printf("hsync = %d-%d kHz, ",
				       timing[5], timing[6]);
				printf("vsync = %d-%d Hz.",
				       timing[7], timing[8]);
			}
			printf("\n");
		}
	}
	vm86_ram_free(memory);
	return 0;
}
