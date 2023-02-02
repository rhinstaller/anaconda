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
            {_("In Installation destination, you can configure disks to be used as the " +
            "installation target. You must select a minimum of 1 disk for the installation" +
            "process to proceed.")}
        </Text>

        <Text component={TextVariants.p}>
            {_("Use the Detect disks button to view and configure the local storage devices " +
            "connected after starting the installation process.")}
        </Text>

        <Text component={TextVariants.p}>
            {_("Use the ")}
            <strong>Detect disks</strong>
            {_(" button to view and configure the local storage devices " +
            "connected after starting the installation process.")}
        </Text>

        <Text component={TextVariants.p}>
            {_("The installer determines the total amount of space on all selected disks, and " +
            "creates a Btrfs layout suitable for your system. The specifics of this layout depend " +
            "on whether your system uses BIOS or UEFI firmware and the total free space on disks. " +
            "A ZRAM-based swap is used instead of a disk-based swap partition.")}
        </Text>

    </TextContent>
);
