#include <stdio.h>
#include <stdlib.h>
#include "vbe.h"

int main(int argc, char **argv)
{
	int i, j;
	unsigned char hmin, hmax, vmin, vmax;
	if(argc < 2) {
		fprintf(stderr, "usage: %s [-hsync] [-vsync] [-modelines]\n",
			argv[0]);
		exit(1);
	}
	for(i = 1; i < argc; i++) {
		if(strcmp(argv[i], "-hsync") == 0) {
			vbe_get_edid_ranges(&hmin, &hmax, &vmin, &vmax);
			printf("%d-%d\n", hmin, hmax);
		}
		if(strcmp(argv[i], "-vsync") == 0) {
			vbe_get_edid_ranges(&hmin, &hmax, &vmin, &vmax);
			printf("%d-%d\n", vmin, vmax);
		}
		if(strcmp(argv[i], "-modelines") == 0) {
			struct vbe_modeline* modelines;
			modelines = vbe_get_edid_modelines();
			for(j=0; modelines && (modelines[j].refresh != 0); j++){
				if(modelines[j].modeline) {
					printf("# %dx%d, %1.1fHz\n%s\n",
					       modelines[j].width,
					       modelines[j].height,
					       modelines[j].refresh,
					       modelines[j].modeline);
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
