#ifndef vesamode_h
#define vesamode_h
#include <sys/types.h>
#ident "$Id$"

typedef enum { hsync_neg = 0, hsync_pos } hsync_t;
typedef enum { vsync_neg = 0, vsync_pos } vsync_t;

struct vesa_mode_t {
	u_int16_t number;
	u_int16_t x, y;
	u_int32_t colors;
	const char *text;
	const char *modeline;
};

struct vesa_timing_t {
	u_int16_t x, y;
	float refresh;
	float dotclock;
	u_int16_t timings[8];
	hsync_t hsync;
	vsync_t vsync;
	float hfreq;
	float vfreq;
};

extern struct vesa_mode_t known_vesa_modes[];
extern struct vesa_timing_t known_vesa_timings[];

#endif /* vesamode_h */
