#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/kd.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
#include <fcntl.h>
#include "vbe.h"
#ident "$Id$"

#define VESA_MODE 0x112

int main(int argc, char **argv)
{
	const void *start_state;
	u_int16_t start_mode;
	struct vbe_info *info;
	struct vbe_mode_info *mode_info;
	char fontdata[32 * 512];
	struct consolefontdesc font = {512, 32, fontdata};
	int fd, tty_fd;
	long tty_mode;
	char *lfb;
	int i, j;

	/* Make sure we have VESA on this machine. */
	info = vbe_get_vbe_info();
	if(info == NULL) {
		fprintf(stderr, "VESA BIOS Extensions not detected.\n");
		exit(1);
	}
	fprintf(stderr, "Detected %c%c%c%c %d.%d\n",
		info->signature[0], info->signature[1],
		info->signature[2], info->signature[3],
		info->version[1], info->version[0]);

	/* Open the current tty.  We'll need this for setting fonts. */
	tty_fd = open("/dev/tty", O_RDWR);
	if(tty_fd == -1) {
		perror("opening tty");
		exit(1);
	}

	/* Save the current VESA state and mode. */
	start_state = vbe_save_svga_state();
	start_mode = vbe_get_mode();

	/* Make sure we don't have garbage values for these. */
	assert(start_state);
	assert(start_mode);
	printf("Started in mode 0x%04x.\n", start_mode);

	/* Make sure the desired mode is available. */
	mode_info = vbe_get_mode_info(VBE_LINEAR_FRAMEBUFFER | VESA_MODE);
	assert(mode_info != NULL);
	assert(mode_info->linear_buffer_address != 0);

	/* Memory-map the framebuffer for direct access (whee!) */
	fd = open("/dev/mem", O_RDWR);
	if(fd == -1) {
		perror("opening framebuffer");
		exit(1);
	}
	lfb = mmap(NULL,
		   mode_info->bytes_per_scanline * mode_info->h,
		   PROT_WRITE,
		   MAP_SHARED,
		   fd,
		   mode_info->linear_buffer_address);
	if(lfb == MAP_FAILED) {
		perror("memory-mapping framebuffer");
		exit(1);
	}

	/* Get the console's current mode and font for restoring when we're
	   finished messing with it. */
	if(ioctl(tty_fd, KDGETMODE, &tty_mode) != 0) {
		perror("getting console mode");
		exit(1);
	}
	if(ioctl(tty_fd, GIO_FONTX, &font) != 0) {
		perror("saving console font");
		exit(1);
	}

	/* Tell the console we're going into graphics mode. */
	if(ioctl(tty_fd, KDSETMODE, KD_GRAPHICS) != 0) {
		perror("preparing for graphics");
		exit(1);
	}

	/* Do the switch. */
	fprintf(stderr, "Switching to mode 0x%04x: %dx%d, %d-bit...\n",
		VBE_LINEAR_FRAMEBUFFER | VESA_MODE,
		mode_info->w, mode_info->h, mode_info->bpp);
	vbe_set_mode(VBE_LINEAR_FRAMEBUFFER | VESA_MODE);

	/* Test pattern time! */
	for(i = 0; i < mode_info->h; i++)
	for(j = 0; j < mode_info->w; j++) {
		lfb[3 * (i * mode_info->w + j) + 0] = j % 256;
		lfb[3 * (i * mode_info->w + j) + 1] = j % 128;
		lfb[3 * (i * mode_info->w + j) + 2] = j % 64;
	}

	/* Pause to admire the display. */
	sleep(10);

	/* Restore the original video mode, hardware settings,
	   VT mode and font. */
	vbe_set_mode(start_mode);
	vbe_restore_svga_state(start_state);
	fprintf(stderr, "Back to normal.\n");

	if(ioctl(tty_fd, KDSETMODE, tty_mode) != 0) {
		perror("switching vt back to normal mode");
	}
	if(ioctl(tty_fd, PIO_FONTX, &font) != 0) {
		perror("restoring console font");
		system("setfont");
	}

	return 0;
}
