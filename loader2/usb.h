#ifndef H_USB
#define H_USB

int usbInitialize(moduleList modLoaded, moduleDeps modDeps,
		  moduleInfoSet modInfo);
void usbInitializeMouse(moduleList modLoaded, moduleDeps modDeps,
                        moduleInfoSet modInfo);

#endif
