#include <sys/types.h>
#include <sys/io.h>
#include <sys/mman.h>
#include <netinet/in.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include <limits.h>
#include <ctype.h>
#include "lrmi.h"
#include "vesamode.h"
#include "vbe.h"
#ident "$Id$"

/* Return information about a particular video mode. */
struct vbe_mode_info *vbe_get_mode_info(u_int16_t mode)
{
	struct LRMI_regs regs;
	char *mem;
	struct vbe_mode_info *ret = NULL;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return NULL;
	}

	/* Allocate a chunk of memory. */
	mem = LRMI_alloc_real(sizeof(struct vbe_mode_info));
	if(mem == NULL) {
		return NULL;
	}
	memset(mem, 0, sizeof(struct vbe_mode_info));

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f01;
	regs.ecx = mode;
	regs.es = ((u_int32_t)mem) >> 4;
	regs.edi = ((u_int32_t)mem) & 0x0f;

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Check for successful return. */
	if((regs.eax & 0xffff) != 0x004f) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Get memory for return. */
	ret = malloc(sizeof(struct vbe_mode_info));
	if(ret == NULL) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Copy the buffer for return. */
	memcpy(ret, mem, sizeof(struct vbe_mode_info));

	/* Clean up and return. */
	LRMI_free_real(mem);
	return ret;
}

/* Get VBE info. */
struct vbe_info *vbe_get_vbe_info()
{
	struct LRMI_regs regs;
	unsigned char *mem;
	struct vbe_info *ret = NULL;
	int i;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return NULL;
	}

	/* Allocate a chunk of memory. */
	mem = LRMI_alloc_real(sizeof(struct vbe_mode_info));
	if(mem == NULL) {
		return NULL;
	}
	memset(mem, 0, sizeof(struct vbe_mode_info));

	/* Set up registers for the interrupt call. */
	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f00;
	regs.es = ((u_int32_t)mem) >> 4;
	regs.edi = ((u_int32_t)mem) & 0x0f;
	memcpy(mem, "VBE2", 4);

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Check for successful return code. */
	if((regs.eax & 0xffff) != 0x004f) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Get memory to return the information. */
	ret = malloc(sizeof(struct vbe_info));
	if(ret == NULL) {
		LRMI_free_real(mem);
		return NULL;
	}
	memcpy(ret, mem, sizeof(struct vbe_info));

	/* Set up pointers to usable memory. */
	ret->mode_list.list = (u_int16_t*) ((ret->mode_list.addr.seg << 4) +
					    (ret->mode_list.addr.ofs));
	ret->oem_name.string = (char*) ((ret->oem_name.addr.seg << 4) +
					(ret->oem_name.addr.ofs));

	/* Snip, snip. */
	mem = strdup(ret->oem_name.string); /* leak */
	while(((i = strlen(mem)) > 0) && isspace(mem[i - 1])) {
		mem[i - 1] = '\0';
	}
	ret->oem_name.string = mem;

	/* Set up pointers for VESA 3.0+ strings. */
	if(ret->version[1] >= 3) {

		/* Vendor name. */
		ret->vendor_name.string = (char*)
			 ((ret->vendor_name.addr.seg << 4)
			+ (ret->vendor_name.addr.ofs));

		mem = strdup(ret->vendor_name.string); /* leak */
		while(((i = strlen(mem)) > 0) && isspace(mem[i - 1])) {
			mem[i - 1] = '\0';
		}
		ret->vendor_name.string = mem;

		/* Product name. */
		ret->product_name.string = (char*)
			 ((ret->product_name.addr.seg << 4)
			+ (ret->product_name.addr.ofs));

		mem = strdup(ret->product_name.string); /* leak */
		while(((i = strlen(mem)) > 0) && isspace(mem[i - 1])) {
			mem[i - 1] = '\0';
		}
		ret->product_name.string = mem;

		/* Product revision. */
		ret->product_revision.string = (char*)
			 ((ret->product_revision.addr.seg << 4)
			+ (ret->product_revision.addr.ofs));

		mem = strdup(ret->product_revision.string); /* leak */
		while(((i = strlen(mem)) > 0) && isspace(mem[i - 1])) {
			mem[i - 1] = '\0';
		}
		ret->product_revision.string = mem;
	}

	/* Cleanup. */
	LRMI_free_real(mem);
	return ret;
}

/* Check if EDID queries are suorted. */
int vbe_get_edid_supported()
{
	struct LRMI_regs regs;
	int ret = 0;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return 0;
	}

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f15;
	regs.ebx = 0x0000;
	regs.es = 0x0000;
	regs.edi = 0x0000;

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		return 0;
	}

	/* Check for successful return. */
	if((regs.eax & 0xff) == 0x4f) {
		/* Supported. */
		ret = 1;
	} else {
		/* Not supported. */
		ret = 0;
	}

	/* Clean up and return. */
	return ret;
}

/* Get EDID info. */
struct vbe_edid1_info *vbe_get_edid_info()
{
	struct LRMI_regs regs;
	unsigned char *mem;
	struct vbe_edid1_info *ret = NULL;
	u_int16_t man;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return NULL;
	}

	/* Allocate a chunk of memory. */
	mem = LRMI_alloc_real(sizeof(struct vbe_edid1_info));
	if(mem == NULL) {
		return NULL;
	}
	memset(mem, 0, sizeof(struct vbe_edid1_info));

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f15;
	regs.ebx = 0x0001;
	regs.es = ((u_int32_t)mem) >> 4;
	regs.edi = ((u_int32_t)mem) & 0x0f;

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		LRMI_free_real(mem);
		return NULL;
	}

#if 0
	/* Check for successful return. */
	if((regs.eax & 0xffff) != 0x004f) {
		LRMI_free_real(mem);
		return NULL;
	}
#elseif
	/* Check for successful return. */
	if((regs.eax & 0xff) != 0x4f) {
		LRMI_free_real(mem);
		return NULL;
	}
#endif

	/* Get memory for return. */
	ret = malloc(sizeof(struct vbe_edid1_info));
	if(ret == NULL) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Copy the buffer for return. */
	memcpy(ret, mem, sizeof(struct vbe_edid1_info));

	memcpy(&man, &ret->manufacturer_name, 2);
	man = ntohs(man);
	memcpy(&ret->manufacturer_name, &man, 2);

	LRMI_free_real(mem);
	return ret;
}

/* Figure out what the current video mode is. */
int32_t vbe_get_mode()
{
	struct LRMI_regs regs;
	int32_t ret = -1;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return -1;
	}

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f03;

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		return -1;
	}

	/* Save the returned value. */
	if((regs.eax & 0xffff) == 0x004f) {
		ret = regs.ebx & 0xffff;
	} else {
		ret = -1;
	}

	/* Clean up and return. */
	return ret;
}

/* Set the video mode. */
void vbe_set_mode(u_int16_t mode)
{
	struct LRMI_regs regs;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return;
	}

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f02;
	regs.ebx = mode;

	/* Do it. */
	iopl(3);
	ioperm(0, 0x400, 1);
	LRMI_int(0x10, &regs);

	/* Return. */
	return;
}

/* Just read ranges from the EDID. */
void vbe_get_edid_ranges(unsigned char *hmin, unsigned char *hmax,
			 unsigned char *vmin, unsigned char *vmax)
{
	struct vbe_edid1_info *edid;
	struct vbe_edid_monitor_descriptor *monitor;
	int i;

	*hmin = *hmax = *vmin = *vmax = 0;

	if((edid = vbe_get_edid_info()) == NULL) {
		return;
	}

	for(i = 0; i < 4; i++) {
		monitor = &edid->monitor_details.monitor_descriptor[i];
		if(monitor->type == vbe_edid_monitor_descriptor_range) {
			*hmin = monitor->data.range_data.horizontal_min;
			*hmax = monitor->data.range_data.horizontal_max;
			*vmin = monitor->data.range_data.vertical_min;
			*vmax = monitor->data.range_data.vertical_max;
		}
	}
}

static int compare_vbe_modelines(const void *m1, const void *m2)
{
	const struct vbe_modeline *M1 = (const struct vbe_modeline*) m1;
	const struct vbe_modeline *M2 = (const struct vbe_modeline*) m2;
	if(M1->width < M2->width) return -1;
	if(M1->width > M2->width) return 1;
	return 0;
}

struct vbe_modeline *vbe_get_edid_modelines()
{
	struct vbe_edid1_info *edid;
	struct vbe_modeline *ret;
	char buf[LINE_MAX];
	int modeline_count = 0, i, j;

	if((edid = vbe_get_edid_info()) == NULL) {
		return NULL;
	}

	memcpy(buf, &edid->established_timings,
	       sizeof(edid->established_timings));
	for(i = 0; i < (8 * sizeof(edid->established_timings)); i++) {
		if(buf[i / 8] & (1 << (i % 8))) {
			modeline_count++;
		}
	}

	/* Count the number of standard timings. */
	for(i = 0; i < 8; i++) {
		int x, v;
		x = edid->standard_timing[i].xresolution;
		v = edid->standard_timing[i].vfreq;
		if(((edid->standard_timing[i].xresolution & 0x01) != x) &&
		   ((edid->standard_timing[i].vfreq & 0x01) != v)) {
			modeline_count++;
		}
	}

	ret = malloc(sizeof(struct vbe_modeline) * (modeline_count + 1));
	if(ret == NULL) {
		return NULL;
	}
	memset(ret, 0, sizeof(struct vbe_modeline) * (modeline_count + 1));

	modeline_count = 0;

	/* Fill out established timings. */
	if(edid->established_timings.timing_720x400_70) {
		ret[modeline_count].width = 720;
		ret[modeline_count].height = 400;
		ret[modeline_count].refresh = 70;
		modeline_count++;
	}
	if(edid->established_timings.timing_720x400_88) {
		ret[modeline_count].width = 720;
		ret[modeline_count].height = 400;
		ret[modeline_count].refresh = 88;
		modeline_count++;
	}
	if(edid->established_timings.timing_640x480_60) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings.timing_640x480_67) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 67;
		modeline_count++;
	}
	if(edid->established_timings.timing_640x480_72) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 72;
		modeline_count++;
	}
	if(edid->established_timings.timing_640x480_75) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings.timing_800x600_56) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 56;
		modeline_count++;
	}
	if(edid->established_timings.timing_800x600_60) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings.timing_800x600_72) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 72;
		modeline_count++;
	}
	if(edid->established_timings.timing_800x600_75) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings.timing_832x624_75) {
		ret[modeline_count].width = 832;
		ret[modeline_count].height = 624;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings.timing_1024x768_87i) {
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 87;
		ret[modeline_count].interlaced = 1;
		modeline_count++;
	}
	if(edid->established_timings.timing_1024x768_60){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings.timing_1024x768_70){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 70;
		modeline_count++;
	}
	if(edid->established_timings.timing_1024x768_75){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings.timing_1280x1024_75) {
		ret[modeline_count].width = 1280;
		ret[modeline_count].height = 1024;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}

	/* Add in standard timings. */
	for(i = 0; i < 8; i++) {
		float aspect = 1;
		int x, v;
		x = edid->standard_timing[i].xresolution;
		v = edid->standard_timing[i].vfreq;
		if(((edid->standard_timing[i].xresolution & 0x01) != x) &&
		   ((edid->standard_timing[i].vfreq & 0x01) != v)) {
			switch(edid->standard_timing[i].aspect) {
				case aspect_75: aspect = 0.7500; break;
				case aspect_8: aspect = 0.8000; break;
				case aspect_5625: aspect = 0.5625; break;
				default: aspect = 1; break;
			}
			x = (edid->standard_timing[i].xresolution + 31) * 8;
			ret[modeline_count].width = x;
			ret[modeline_count].height = x * aspect;
			ret[modeline_count].refresh =
				edid->standard_timing[i].vfreq + 60;
			modeline_count++;
		}
	}

	/* Now tack on any matching modelines. */
	for(i = 0; ret[i].refresh != 0; i++) {
		struct vesa_timing_t *t = NULL;
		for(j = 0; known_vesa_timings[j].refresh != 0; j++) {
			t = &known_vesa_timings[j];
			if(ret[i].width == t->x)
			if(ret[i].height == t->y)
			if(ret[i].refresh == t->refresh) {
				snprintf(buf, sizeof(buf),
					 "ModeLine \"%dx%d\"\t%6.2f "
					 "%4d %4d %4d %4d %4d %4d %4d %4d %s %s"
					 , t->x, t->y, t->dotclock,
					 t->timings[0],
					 t->timings[0] + t->timings[1],
					 t->timings[0] + t->timings[1] +
					 t->timings[2],
					 t->timings[0] + t->timings[1] +
					 t->timings[2] + t->timings[3],
					 t->timings[4],
					 t->timings[4] + t->timings[5],
					 t->timings[4] + t->timings[5] +
					 t->timings[6],
					 t->timings[4] + t->timings[5] +
					 t->timings[6] + t->timings[7],
					 t->hsync == hsync_pos ?
					 "+hsync" : "-hsync",
					 t->vsync == vsync_pos ?
					 "+vsync" : "-vsync");
				ret[i].modeline = strdup(buf);
				ret[i].hfreq = t->hfreq;
				ret[i].vfreq = t->vfreq;
			}
		}
	}

	modeline_count = 0;
	for(i = 0; ret[i].refresh != 0; i++) {
		modeline_count++;
	}
	qsort(ret, modeline_count, sizeof(ret[0]), compare_vbe_modelines);

	return ret;
}

const void *vbe_save_svga_state()
{
	struct LRMI_regs regs;
	unsigned char *mem;
	u_int16_t block_size;
	void *data;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return NULL;
	}

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f04;
	regs.ecx = 0xffff;
	regs.edx = 0;

	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		return NULL;
	}

	if((regs.eax & 0xff) != 0x4f) {
		fprintf(stderr, "Get SuperVGA Video State not supported.\n");
		return NULL;
	}

	if((regs.eax & 0xffff) != 0x004f) {
		fprintf(stderr, "Get SuperVGA Video State Info failed.\n");
		return NULL;
	}

	block_size = 64 * (regs.ebx & 0xffff);

	/* Allocate a chunk of memory. */
	mem = LRMI_alloc_real(block_size);
	if(mem == NULL) {
		return NULL;
	}
	memset(mem, 0, sizeof(block_size));
	
	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f04;
	regs.ecx = 0x000f;
	regs.edx = 0x0001;
	regs.es  = ((u_int32_t)mem) >> 4;
	regs.ebx = ((u_int32_t)mem) & 0x0f;
	memset(mem, 0, block_size);
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		LRMI_free_real(mem);
		return NULL;
	}

	if((regs.eax & 0xffff) != 0x004f) {
		fprintf(stderr, "Get SuperVGA Video State Save failed.\n");
		return NULL;
	}

	data = malloc(block_size);
	if(data == NULL) {
		LRMI_free_real(mem);
		return NULL;
	}

	/* Clean up and return. */
	memcpy(data, mem, block_size);
	LRMI_free_real(mem);
	return data;
}

void vbe_restore_svga_state(const void *state)
{
	struct LRMI_regs regs;
	unsigned char *mem;
	u_int16_t block_size;

	/* Initialize LRMI. */
	if(LRMI_init() == 0) {
		return;
	}

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f04;
	regs.ecx = 0x000f;
	regs.edx = 0;

	/* Find out how much memory we need. */
	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		return;
	}

	if((regs.eax & 0xff) != 0x4f) {
		fprintf(stderr, "Get SuperVGA Video State not supported.\n");
		return;
	}

	if((regs.eax & 0xffff) != 0x004f) {
		fprintf(stderr, "Get SuperVGA Video State Info failed.\n");
		return;
	}

	block_size = 64 * (regs.ebx & 0xffff);

	/* Allocate a chunk of memory. */
	mem = LRMI_alloc_real(block_size);
	if(mem == NULL) {
		return;
	}
	memset(mem, 0, sizeof(block_size));

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f04;
	regs.ecx = 0x000f;
	regs.edx = 0x0002;
	regs.es  = 0x2000;
	regs.ebx = 0x0000;
	memcpy(mem, state, block_size);

	iopl(3);
	ioperm(0, 0x400, 1);

	if(LRMI_int(0x10, &regs) == 0) {
		LRMI_free_real(mem);
		return;
	}

	if((regs.eax & 0xffff) != 0x004f) {
		fprintf(stderr, "Get SuperVGA Video State Restore failed.\n");
		return;
	}
}
