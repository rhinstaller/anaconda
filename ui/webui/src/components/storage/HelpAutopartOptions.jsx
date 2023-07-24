import cockpit from "cockpit";

const _ = cockpit.gettext;

export const helpEraseAll = _("Remove all partitions on the selected devices, including existing operating systems. Make sure you have backed up your data.");

export const helpUseFreeSpace = _("Keeps current disk layout and uses only available space.");

export const helpCustomMountPoint = _("This option requires that the selected device has formated partitions.");
