#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vbe.h"

int main(int argc, char **argv)
{
	int i, j;
	unsigned char hmin, hmax, vmin, vmax;
	if(argc < 2) {
		char *p = argv[0];
		if(strchr(p, '/')) {
			p = strchr(p, '/');
			p++;
		}
		fprintf(stderr,"syntax: %s [-hsync] [-vsync] [-modelines]\n",p);
		exit(1);
	}
	for(i = 1; i < argc; i++) {
		if(strcmp(argv[i], "-hsync") == 0) {
			vbe_get_edid_ranges(&hmin, &hmax, &vmin, &vmax);
			if(hmin || hmax)
				printf("%d-%d\n", hmin, hmax);
		}
		if(strcmp(argv[i], "-vsync") == 0) {
			vbe_get_edid_ranges(&hmin, &hmax, &vmin, &vmax);
			if(vmin || vmax)
				printf("%d-%d\n", vmin, vmax);
		}
		if(strcmp(argv[i], "-modelines") == 0) {
			struct vbe_modeline* modelines;
			modelines = vbe_get_edid_modelines();
			for(j=0; modelines && (modelines[j].refresh != 0); j++){
				if(modelines[j].modeline) {
					printf("# %dx%d, %1.1fHz%s\n%s\n",
					       modelines[j].width,
					       modelines[j].height,
					       modelines[j].refresh,
					       modelines[j].modeline,
					       modelines[j].interlaced?"i":"");
					free(modelines[j].modeline);
				}
			}
			if(modelines) {
				free(modelines);
			}
		}
	}
	return 0;
}
