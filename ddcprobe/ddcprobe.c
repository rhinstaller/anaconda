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
	struct vbe_info *vbe_info = NULL;
	struct vbe_edid_info *edid_info = NULL;
	u_int16_t *mode_list = NULL;
	char manufacturer[4];
	int i;

	vbe_info = vbe_get_vbe_info();
	if(vbe_info == NULL) {
		printf("VESA BIOS Extensions not detected.\n");
		exit(0);
	}

	/* Signature. */
	printf("%c%c%c%c %d.%d detected.\n",
	       vbe_info->signature[0], vbe_info->signature[1],
	       vbe_info->signature[2], vbe_info->signature[3],
	       vbe_info->version[1], vbe_info->version[0]);

	/* OEM */
	printf("OEM Name: %s\n", vbe_info->oem_name.string);

	/* Memory. */
	printf("Memory installed = %d * 64k blocks = %dkb\n",
	       vbe_info->memory_size, vbe_info->memory_size * 64);

	/* List supported standard modes. */
	mode_list = vbe_info->mode_list.list;
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

	if(!vbe_get_edid_supported()) {
		printf("EDID read not supported by video card.\n");
		exit(0);
	}

	edid_info = vbe_get_edid_info();

	/* Interpret results. */
	if(edid_info == NULL) {
		printf("EDID failed. (No DDC-capable monitor attached?)\n");
		exit(0);
	}

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
	printf("Serial number: %08x.\n", edid_info->serial);

	printf("Manufactured in week %d of %d.\n",
	       edid_info->week, edid_info->year + 1990);

	printf("Input signal type: %s%s%s%s.\n",
	       edid_info->video_input.separate_sync ? "separate sync, " : "",
	       edid_info->video_input.composite_sync ? "composite sync, " : "",
	       edid_info->video_input.sync_on_green ? "sync on green, " : "",
	       edid_info->video_input.digital ?
	       "digital signal" : "analog signal");

	printf("Screen size max %d cm horizontal, %d cm vertical.\n",
	       edid_info->max_size_horizontal,
	       edid_info->max_size_vertical);

	printf("Gamma: %f.\n", edid_info->gamma / 100.0 + 1);

	printf("DPMS flags: %s, %s%s, %s%s, %s%s.\n",
	       edid_info->dpms_flags.rgb ? "RGB" : "non-RGB",
	       edid_info->dpms_flags.active_off ? "" : "no ", "active off",
	       edid_info->dpms_flags.suspend ? "" : "no ", "suspend",
	       edid_info->dpms_flags.standby ? "" : "no ", "standby");

	printf("Established timings:\n");
	if(edid_info->established_timings.timing_720x400_70)
		printf("\t720x400 @ 70 Hz (VGA 640x400, IBM)\n");
	if(edid_info->established_timings.timing_720x400_88)
		printf("\t720x400 @ 88 Hz (XGA2)\n");
	if(edid_info->established_timings.timing_640x480_60)
		printf("\t640x480 @ 60 Hz (VGA)\n");
	if(edid_info->established_timings.timing_640x480_67)
		printf("\t640x480 @ 67 Hz (Mac II, Apple)\n");
	if(edid_info->established_timings.timing_640x480_72)
		printf("\t640x480 @ 72 Hz (VESA)\n");
	if(edid_info->established_timings.timing_640x480_75)
		printf("\t640x480 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings.timing_800x600_56)
		printf("\t800x600 @ 56 Hz (VESA)\n");
	if(edid_info->established_timings.timing_800x600_60)
		printf("\t800x600 @ 60 Hz (VESA)\n");
	if(edid_info->established_timings.timing_800x600_72)
		printf("\t800x600 @ 72 Hz (VESA)\n");
	if(edid_info->established_timings.timing_800x600_75)
		printf("\t800x600 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings.timing_832x624_75)
		printf("\t832x624 @ 75 Hz (Mac II)\n");
	if(edid_info->established_timings.timing_1024x768_87i)
		printf("\t1024x768 @ 87 Hz Interlaced (8514A)\n");
	if(edid_info->established_timings.timing_1024x768_60)
		printf("\t1024x768 @ 60 Hz (VESA)\n");
	if(edid_info->established_timings.timing_1024x768_70)
		printf("\t1024x768 @ 70 Hz (VESA)\n");
	if(edid_info->established_timings.timing_1024x768_75)
		printf("\t1024x768 @ 75 Hz (VESA)\n");
	if(edid_info->established_timings.timing_1280x1024_75)
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
	return 0;
}
