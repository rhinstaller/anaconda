#include <sys/types.h>
#include <sys/vm86.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include <limits.h>
#include "bioscall.h"
#include "vesamode.h"
#include "vbe.h"
#ident "$Id$"

struct vbe_mode_info *vbe_get_mode_info(u_int16_t mode)
{
	struct vm86_regs regs;
	unsigned char *ram;
	struct vbe_mode_info *ret = NULL;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f01;
	regs.ecx = mode;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return NULL;
	}
	memset(&ram[regs.es * 16 + regs.edi], 0, 1024);

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Check for successful return. */
	if((regs.eax & 0xffff) != 0x004f) {
		vm86_ram_free(ram);
		return NULL;
	}

	/* Get memory for return. */
	ret = malloc(sizeof(struct vbe_mode_info));
	if(ret == NULL) {
		vm86_ram_free(ram);
		return NULL;
	}

	/* Copy the buffer for return. */
	memcpy(ret, &ram[regs.es*16 + regs.edi], sizeof(struct vbe_mode_info));

	/* Clean up and return. */
	vm86_ram_free(ram);
	return ret;
}

struct vbe_info *vbe_get_vbe_info()
{
	struct vm86_regs regs;
	unsigned char *ram;
	struct vbe_info *ret = NULL;
	u_int16_t *modes;
	int mode_count = 0;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f00;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return NULL;
	}
	memset(&ram[regs.es * 16 + regs.edi], 0, 1024);

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Check for successful return code. */
	if((regs.eax & 0xffff) != 0x004f) {
		vm86_ram_free(ram);
		return NULL;
	}

	/* Count the number of supported video modes. */
	ret = (struct vbe_info*) &ram[regs.es * 16 + regs.edi];
	modes = (u_int16_t*) &ram[ret->mode_list.addr.seg * 16 +
				  ret->mode_list.addr.ofs];
	for(mode_count = 0; (*modes != 0xffff); modes++) {
		mode_count++;
	}
	modes = (u_int16_t*) &ram[ret->mode_list.addr.seg * 16 +
				  ret->mode_list.addr.ofs];

	/* Get enough memory to hold the mode list, too. */
	ret = malloc(sizeof(struct vbe_info) +
		     (mode_count + 1) * sizeof(u_int16_t) +
		     strlen(&ram[ret->oem_name.addr.seg * 16 +
				 ret->oem_name.addr.ofs]));
	if(ret == NULL) {
		vm86_ram_free(ram);
		return NULL;
	}

	/* Copy the static parts of the buffer out. */
	memcpy(ret, &ram[regs.es * 16 + regs.edi], sizeof(struct vbe_info));

	/* Copy the modes list and set the pointer to it. */
	memcpy(ret + 1, modes, (mode_count + 1) * sizeof(u_int16_t));
	ret->mode_list.list = (u_int16_t*) (ret + 1);
	memcpy(&ret->mode_list.list[mode_count + 1],
	       &ram[ret->oem_name.addr.seg * 16 + ret->oem_name.addr.ofs],
	       strlen(&ram[ret->oem_name.addr.seg*16+ret->oem_name.addr.ofs]));
	ret->oem_name.string = (char*) &ret->mode_list.list[mode_count + 1];

	vm86_ram_free(ram);
	return ret;
}

int vbe_get_edid_supported()
{
	struct vm86_regs regs;
	unsigned char *ram;
	int ret = 0;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f15;
	regs.ebx = 0x0000;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return 0;
	}

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Check for successful return. */
	if((regs.eax & 0xff) == 0x4f) {
		/* Supported. */
		ret = 1;
	} else {
		/* Not supported. */
		ret = 0;
	}

	/* Clean up and return. */
	vm86_ram_free(ram);
	return ret;
}

struct vbe_edid_info *vbe_get_edid_info()
{
	struct vm86_regs regs;
	unsigned char *ram;
	struct vbe_edid_info *ret = NULL;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f15;
	regs.ebx = 0x0001;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return NULL;
	}
	memset(&ram[regs.es * 16 + regs.edi], 0, 1024);

	/* Do it. */
	bioscall(0x10, &regs, ram);

#if 0
	/* Check for successful return. */
	if((regs.eax & 0xffff) != 0x004f) {
		vm86_ram_free(ram);
		return NULL;
	}
#else
	/* Check for successful return. */
	ret = (struct vbe_edid_info*) &ram[regs.es * 16 + regs.edi];
	if(ret->manufacturer == 0) {
		vm86_ram_free(ram);
		return NULL;
	}
#endif

	/* Get memory for return. */
	ret = malloc(sizeof(struct vbe_edid_info));
	if(ret == NULL) {
		vm86_ram_free(ram);
		return NULL;
	}

	/* Copy the buffer for return. */
	memcpy(ret, &ram[regs.es*16 + regs.edi], sizeof(struct vbe_edid_info));
	vm86_ram_free(ram);
	return ret;
}

int32_t vbe_get_mode()
{
	struct vm86_regs regs;
	unsigned char *ram;
	int32_t ret = -1;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f03;

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return -1;
	}

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Save the returned value. */
	if((regs.eax & 0xffff) == 0x004f) {
		ret = regs.ebx && 0xffff;
	} else {
		ret = -1;
	}

	/* Clean up and return. */
	vm86_ram_free(ram);
	return ret;
}

void vbe_set_mode(u_int16_t mode)
{
	struct vm86_regs regs;
	unsigned char *ram;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f02;
	regs.ebx = mode;

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return;
	}

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Clean up and return. */
	vm86_ram_free(ram);
	return;
}

void vbe_get_edid_ranges(unsigned char *hmin, unsigned char *hmax,
			 unsigned char *vmin, unsigned char *vmax)
{
	struct vbe_edid_info *edid;
	const unsigned char *timing;
	int i;

	*hmin = *hmax = *vmin = *vmax = 0;

	if((edid = vbe_get_edid_info()) == NULL) {
		return;
	}

	for(i = 0; i < 4; i++) {
		timing = edid->detailed_timing[i];
		if(!timing[0] && !timing[1] && !timing[2]) {
			if(timing[3] == VBE_EDID_TEXT_RANGES) {
				*vmin = timing[5];
				*vmax = timing[6];
				*hmin = timing[7];
				*hmax = timing[8];
			}
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
	struct vbe_edid_info *edid;
	struct vbe_modeline *ret;
	char buf[LINE_MAX];
	int modeline_count = 0, i, j;

	if((edid = vbe_get_edid_info()) == NULL) {
		return NULL;
	}

	for(i = 0; i < 8; i++) {
		if(edid->established_timings1 & (1 << i)) {
			modeline_count++;
		}
		if(edid->established_timings2 & (1 << i)) {
			modeline_count++;
		}
		if((edid->standard_timing[i].xresolution >= 2) ||
		   (edid->standard_timing[i].vfreq >= 2)) {
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
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_720x400_70) {
		ret[modeline_count].width = 720;
		ret[modeline_count].height = 400;
		ret[modeline_count].refresh = 70;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_720x400_88) {
		ret[modeline_count].width = 720;
		ret[modeline_count].height = 400;
		ret[modeline_count].refresh = 88;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_640x480_60) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_640x480_67) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 67;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_640x480_72) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 72;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_640x480_75) {
		ret[modeline_count].width = 640;
		ret[modeline_count].height = 480;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_800x600_56) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 56;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING1_800x600_60) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_800x600_72) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 72;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_800x600_75) {
		ret[modeline_count].width = 800;
		ret[modeline_count].height = 600;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_832x624_75) {
		ret[modeline_count].width = 832;
		ret[modeline_count].height = 624;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_1024x768_87i) {
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 87;
		ret[modeline_count].interlaced = 1;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_1024x768_60){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 60;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_1024x768_70){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 70;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_1024x768_75){
		ret[modeline_count].width = 1024;
		ret[modeline_count].height = 768;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}
	if(edid->established_timings1&VBE_EDID_ESTABLISHED_TIMING2_1280x1024_75) {
		ret[modeline_count].width = 1280;
		ret[modeline_count].height = 1024;
		ret[modeline_count].refresh = 75;
		modeline_count++;
	}

	/* Add in standard timings. */
	for(i = 0; i < 8; i++) {
		float aspect = 1;
		int x;
		if((edid->standard_timing[i].xresolution >= 2) ||
		   (edid->standard_timing[i].vfreq >= 2)) {
			switch(edid->standard_timing[i].vfreq >> 6) {
				case 1: aspect = 0.7500; break;
				case 2: aspect = 0.8000; break;
				case 3: aspect = 0.5625; break;
				default: aspect = 1; break;
			}
			x = (edid->standard_timing[i].xresolution + 31) * 8;
			ret[modeline_count].width = x;
			ret[modeline_count].height = x * aspect;
			ret[modeline_count].refresh =
				(edid->standard_timing[i].vfreq & 0x1f) + 60;
			modeline_count++;
		}
	}

	/* Now tack on any matching modelines. */
	for(i = 0; ret[i].refresh != 0; i++) {
		struct vesa_timing_t *t = NULL;
		for(j = 0; known_vesa_timings[j].refresh != 0; j++) {
			if(ret[i].width == known_vesa_timings[j].x)
			if(ret[i].height == known_vesa_timings[j].y)
			if(ret[i].refresh == known_vesa_timings[j].refresh) {
				t = &known_vesa_timings[j];
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
