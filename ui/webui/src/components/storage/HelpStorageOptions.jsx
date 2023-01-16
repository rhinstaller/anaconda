import React from "react";
import cockpit from "cockpit";

import {
    Text,
    TextContent,
    TextVariants,
    Title,
} from "@patternfly/react-core";

const _ = cockpit.gettext;

export const helpStorageOptions = (
    <TextContent>
        <Title headingLevel="h2">
            {_("Storage options")}
        </Title>
        <Text component={TextVariants.p}>
            {_("Installation destination allows you to configure which disks will be used " +
            "as the installation target for your Fedora installation. At least 1 disk must " +
            "be selected for the installation to proceed.")}
        </Text>
        <Text component={TextVariants.p}>
            {_("All locally available storage devices (SATA, IDE and SCSI hard drives, USB " +
            "flash drives, etc.) are displayed in the Local Standard Disks section. Local " +
            "disks are detected when the installer starts - any storage devices connected " +
            "after the installation has started will not be shown.")}
        </Text>
        <Text component={TextVariants.p}>
            {_("If you need to configure additional local storage devices, refresh the " +
            "device list using the Detect disks button. All detected disks, including any new ones, " +
            "will be displayed in the Local Standard Disks section.")}
        </Text>
        <Text>
            {_("The installer will determine the total amount of space on all selected " +
            "disks, and it will create a Btrfs layout suitable for your system. The " +
            "specifics of this layout depend on whether your system uses BIOS or UEFI " +
            "firmware, and the total amount of free space on your disks. A ZRAM-based " +
            "swap will be used instead of a disk-based swap partition.")}
        </Text>
    </TextContent>
);
