#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
#include <fcntl.h>
#include "vbe.h"

int main(int argc, char **argv)
{
	const void *start_state;
	u_int16_t start_mode;
	struct vbe_info *info;
	struct vbe_mode_info *mode_info;
	int fd;
	char *lfb;
	int i, j;

	start_state = vbe_save_svga_state();
	start_mode = vbe_get_mode();

	assert(start_state);
	assert(start_mode);
	printf("Starting in mode %d.\n", start_mode);

	mode_info = vbe_get_mode_info(VBE_LINEAR_FRAMEBUFFER | 0x112);
	assert(mode_info != NULL);

	printf("Switching...\n");

	fd = open("/dev/mem", O_RDWR);
	if(fd == -1) {
		perror("opening framebuffer");
		exit(1);
	}
	assert(mode_info->linear_buffer_address != 0);

	lfb = mmap(NULL,
		   mode_info->bytes_per_scanline * mode_info->h,
		   PROT_WRITE,
		   MAP_SHARED,
		   fd,
		   mode_info->linear_buffer_address);
	assert(lfb != MAP_FAILED);
	sleep(1);

	vbe_set_mode(VBE_LINEAR_FRAMEBUFFER | 0x112);

	for(i = 0; i < mode_info->h; i++)
	for(j = 0; j < mode_info->w; j++) {
		lfb[3 * (i * mode_info->w + j) + 0] = j % 255;
		lfb[3 * (i * mode_info->w + j) + 1] = j % 128;
		lfb[3 * (i * mode_info->w + j) + 2] = j % 64;
	}

	sleep(10);

	vbe_set_mode(start_mode);
	vbe_restore_svga_state(start_state);

	return 0;
}
