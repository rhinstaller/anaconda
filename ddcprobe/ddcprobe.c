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
#include "lrmi.h"
#ident "$Id$"

char *snip(char *string)
{
	int i;
	while(((i = strlen(string)) > 0) &&
	       (isspace(string[i - 1]) ||
	        (string[i - 1] == '\n') ||
	        (string[i - 1] == '\r'))) {
		string[i - 1] = '\0';
	}
	return string;
}

int main(int argc, char **argv)
{
	struct vbe_info *vbe_info = NULL;
	struct vbe_edid1_info *edid_info = NULL;
	u_int16_t *mode_list = NULL;
	char manufacturer[4];
	int i;

	assert(sizeof(struct vbe_info) == 512);
	assert(sizeof(struct vbe_edid1_info) == 256);
	assert(sizeof(struct vbe_edid_detailed_timing) == 18);
	assert(sizeof(struct vbe_edid_monitor_descriptor) == 18);

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

	/* OEM Strings. */
	printf("OEM Name: %s\n", vbe_info->oem_name.string);
	if(vbe_info->version[1] >= 3) {
		printf("Vendor Name: %s\n",
		       vbe_info->vendor_name.string);
		printf("Product Name: %s\n",
		       vbe_info->product_name.string);
		printf("Product Revision: %s\n",
		       vbe_info->product_revision.string);
	}

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
	if((edid_info == NULL) || (edid_info->version == 0)) {
		printf("EDID read failed. (No DDC-capable monitor attached?)\n");
		exit(0);
	}

	printf("EDID ver. %d rev. %d.\n",
	       edid_info->version, edid_info->revision);

	manufacturer[0] = edid_info->manufacturer_name.char1 + 'A' - 1;
	manufacturer[1] = edid_info->manufacturer_name.char2 + 'A' - 1;
	manufacturer[2] = edid_info->manufacturer_name.char3 + 'A' - 1;
	manufacturer[3] = '\0';
	printf("Manufacturer: %s\n", manufacturer);

	if(edid_info->serial_number != 0xffffffff) {
		if(strcmp(manufacturer, "MAG") == 0) {
			edid_info->serial_number -= 0x7000000;
		}
		if(strcmp(manufacturer, "OQI") == 0) {
			edid_info->serial_number -= 456150000;
		}
		if(strcmp(manufacturer, "VSC") == 0) {
			edid_info->serial_number -= 640000000;
		}
	}
	printf("Serial number: %08x.\n", edid_info->serial_number);

	printf("Manufactured in week %d of %d.\n",
	       edid_info->week, edid_info->year + 1990);

	printf("Input signal type: %s%s%s%s.\n",
	       edid_info->video_input_definition.separate_sync ?
	       "separate sync, " : "",
	       edid_info->video_input_definition.composite_sync ?
	       "composite sync, " : "",
	       edid_info->video_input_definition.sync_on_green ?
	       "sync on green, " : "",
	       edid_info->video_input_definition.digital ?
	       "digital signal" : "analog signal");

	printf("Screen size max %d cm horizontal, %d cm vertical.\n",
	       edid_info->max_size_horizontal,
	       edid_info->max_size_vertical);

	printf("Gamma: %f.\n", edid_info->gamma / 100.0 + 1);

	printf("DPMS flags: %s, %s%s, %s%s, %s%s.\n",
	       edid_info->feature_support.rgb ? "RGB" : "non-RGB",
	       edid_info->feature_support.active_off ? "" : "no ", "active off",
	       edid_info->feature_support.suspend ? "" : "no ", "suspend",
	       edid_info->feature_support.standby ? "" : "no ", "standby");

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
			switch(edid_info->standard_timing[i].aspect) {
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
		struct vbe_edid_monitor_descriptor *monitor = NULL;
		struct vbe_edid_detailed_timing *timing = NULL;

		timing = &edid_info->monitor_details.detailed_timing[i];
		monitor = &edid_info->monitor_details.monitor_descriptor[i];

		if((monitor->zero_flag_1 != 0) || (monitor->zero_flag_2 != 0)) {
			printf("Detailed timing %d:\n", i);
			printf("\tPixel clock: %d\n",
			       VBE_EDID_DETAILED_TIMING_PIXEL_CLOCK(*timing));
			printf("\tHorizontal active time (pixel width): %d\n",
			       VBE_EDID_DETAILED_TIMING_HORIZONTAL_ACTIVE(*timing));
			printf("\tHorizontal blank time (pixel width): %d\n",
			       VBE_EDID_DETAILED_TIMING_HORIZONTAL_BLANKING(*timing));
			printf("\tVertical active time (pixel height): %d\n",
			       VBE_EDID_DETAILED_TIMING_VERTICAL_ACTIVE(*timing));
			printf("\tVertical blank time (pixel height): %d\n",
			       VBE_EDID_DETAILED_TIMING_VERTICAL_BLANKING(*timing));
			printf("\tHorizontal sync offset: %d\n",
			       VBE_EDID_DETAILED_TIMING_HSYNC_OFFSET(*timing));
			printf("\tHorizontal sync pulse width: %d\n",
			       VBE_EDID_DETAILED_TIMING_HSYNC_PULSE_WIDTH(*timing));
			printf("\tVertical sync offset: %d\n",
			       VBE_EDID_DETAILED_TIMING_VSYNC_OFFSET(*timing));
			printf("\tVertical sync pulse width: %d\n",
			       VBE_EDID_DETAILED_TIMING_VSYNC_PULSE_WIDTH(*timing));
			printf("\tDimensions: %dx%d\n",
			       VBE_EDID_DETAILED_TIMING_HIMAGE_SIZE(*timing),
			       VBE_EDID_DETAILED_TIMING_VIMAGE_SIZE(*timing));
		} else
		if(monitor->type == vbe_edid_monitor_descriptor_serial) {
			printf("Monitor details %d:\n", i);
			printf("\tSerial number: %s\n",
			       snip(monitor->data.string));
		} else
		if(monitor->type == vbe_edid_monitor_descriptor_ascii) {
			printf("Monitor details %d:\n", i);
			printf("\tASCII String: %s:\n",
			       snip(monitor->data.string));
		} else
		if(monitor->type == vbe_edid_monitor_descriptor_name) {
			printf("Monitor details %d:\n", i);
			printf("\tName: %s\n",
			       snip(monitor->data.string));
		} else
		if(monitor->type == vbe_edid_monitor_descriptor_range) {
			printf("Monitor details %d:\n", i);
			printf("\tTiming ranges: "
			       "horizontal = %d - %d, vertical = %d - %d\n",
			       monitor->data.range_data.horizontal_min,
			       monitor->data.range_data.horizontal_max,
			       monitor->data.range_data.vertical_min,
			       monitor->data.range_data.vertical_max);
		}
	}
	return 0;
}
