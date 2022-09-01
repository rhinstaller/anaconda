/*
 * Copyright (C) 2022 Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with This program; If not, see <http://www.gnu.org/licenses/>.
 */
import cockpit from "cockpit";
import React, { useRef } from "react";

import {
    Drawer,
    DrawerActions,
    DrawerCloseButton,
    DrawerContent,
    DrawerContentBody,
    DrawerHead,
    DrawerPanelContent,
    Text,
    TextContent,
    TextVariants,
    Title
} from "@patternfly/react-core";

const _ = cockpit.gettext;

export const HelpDrawer = ({ isExpanded, setIsExpanded, children }) => {
    const drawerRef = useRef(null);

    const onExpand = () => {
        drawerRef.current && drawerRef.current.focus();
    };

    const onCloseClick = () => {
        setIsExpanded(false);
    };

    const content = (
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
                "page using the refresh icon. All detected disks, including any new ones, " +
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

    const panelContent = (
        <DrawerPanelContent isResizable defaultSize="450px" minSize="150px">
            <DrawerHead>
                <span tabIndex={isExpanded ? 0 : -1} ref={drawerRef}>
                    {content}
                </span>
                <DrawerActions>
                    <DrawerCloseButton onClick={onCloseClick} />
                </DrawerActions>
            </DrawerHead>
        </DrawerPanelContent>
    );

    return (
        <Drawer isExpanded={isExpanded} isInline position="right" onExpand={onExpand}>
            <DrawerContent panelContent={panelContent}>
                <DrawerContentBody>{children}</DrawerContentBody>
            </DrawerContent>
        </Drawer>

    );
};
