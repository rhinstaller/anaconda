#include	<sys/types.h>
#include	<sys/kd.h>
#include	<sys/vt.h>
#include	<sys/ioctl.h>

int main(void)
{
	struct vt_mode vtm;

	ioctl(0, KDSETMODE, KD_TEXT);
	vtm.mode = VT_AUTO;
	vtm.waitv = 0;
	vtm.relsig = 0;
	vtm.acqsig = 0;
	ioctl(0, VT_SETMODE, &vtm);

	return 0;
}
