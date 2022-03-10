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
import React, { useContext, useState } from "react";

import {
    Card, CardBody, CardHeader, CardTitle,
    DataList, DataListItem, DataListItemRow, DataListCheck, DataListItemCells, DataListCell,
    Form,
    Hint, HintBody,
} from "@patternfly/react-core";

import { AddressContext } from "../Common.jsx";
import { useEvent, useObject } from "hooks";

const _ = cockpit.gettext;

/**
 *  Select default disks for the partitioning.
 *
 * If there are some disks already selected, do nothing.
 * In the automatic installation, select all disks. In
 * the interactive installation, select a disk if there
 * is only one available.
 * @return: the list of selected disks
 */
const selectDefaultDisks = ({ ignoredDisks, selectedDisks, usableDisks }) => {
    // FIXME: how to get installation flags?
    const flags = {};

    if (selectedDisks.length) {
        // Do nothing if there are some disks selected
        return [];
    } else if (flags.automatedInstall) {
        // FIXME
        return [];
    } else {
        const availableDisks = usableDisks.filter(disk => !ignoredDisks.includes(disk));

        console.log("Selecting one or less disks by default:", availableDisks.join(","));

        // Select a usable disk if there is only one available
        if (availableDisks.length === 1) {
            return availableDisks;
        }
        return [];
    }
};

const LocalStandardDisks = () => {
    const [deviceData, setDeviceData] = useState({});
    const [selectedDisks, setSelectedDisks] = useState({});
    const [usableDisks, setUsableDisks] = useState();

    const address = useContext(AddressContext);
    const client = cockpit.dbus("org.fedoraproject.Anaconda.Modules.Storage", { superuser: "try", bus: "none", address });

    const diskSelectionProxy = useObject(() => {
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
            "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        );

        return proxy;
    }, null, [address]);

    const deviceTreeViewerProxy = useObject(() => {
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
            "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        );

        return proxy;
    }, null, [address]);

    useEvent(diskSelectionProxy, "changed", (event, data) => {
        diskSelectionProxy
                .GetUsableDisks()
                .then(usableDisks => {
                    setUsableDisks(usableDisks);
                    // Select default disks for the partitioning
                    const defaultDisks = selectDefaultDisks({
                        ignoredDisks: diskSelectionProxy.IgnoredDisks,
                        selectedDisks: diskSelectionProxy.SelectedDisks,
                        usableDisks,
                    });
                    setSelectedDisks(defaultDisks.reduce((acc, cur) => ({ ...acc, [cur]: true }), {}));

                    // Show disks data
                    usableDisks.forEach(disk => {
                        deviceTreeViewerProxy
                                .GetDeviceData(disk)
                                .then(data => {
                                    setDeviceData({ ...deviceData, [disk]: data });
                                }, console.error);
                    });
                }, console.error);
    });

    return (
        <Card>
            <CardHeader>
                <CardTitle>{_("Local standard disks")}</CardTitle>
            </CardHeader>
            <CardBody>
                <DataList isCompact aria-label={_("Usable disks")}>
                    {usableDisks && usableDisks.map(disk => (
                        <DataListItem key={disk} aria-labelledby={"local-disks-checkbox-" + disk}>
                            <DataListItemRow>
                                <DataListCheck
                                  aria-labelledby={"local-disks-checkbox-" + disk}
                                  onChange={value => setSelectedDisks({ ...selectedDisks, [disk]: value })}
                                  checked={!!selectedDisks[disk]}
                                  name={"checkbox-check-" + disk} />
                                <DataListItemCells
                                  dataListCells={[
                                      <DataListCell key={disk} id={"local-disks-item-" + disk}>
                                          {disk}
                                      </DataListCell>,
                                      <DataListCell key={"description-" + disk}>
                                          {deviceData && deviceData[disk] && deviceData[disk].description.v}
                                      </DataListCell>,
                                      <DataListCell key={"size-" + disk}>
                                          {cockpit.format_bytes(deviceData && deviceData[disk] && deviceData[disk].size.v)}
                                      </DataListCell>
                                  ]}
                                />
                            </DataListItemRow>
                        </DataListItem>
                    ))}
                </DataList>
            </CardBody>
        </Card>
    );
};

export const InstallationDestination = () => {
    return (
        <Form isHorizontal>
            <Hint>
                <HintBody>
                    {_("Select the device(s) you would like to install to. They will be left untouched until you click on the main menu's 'Begin installation' button.")}
                </HintBody>
            </Hint>
            <LocalStandardDisks />
        </Form>
    );
};
