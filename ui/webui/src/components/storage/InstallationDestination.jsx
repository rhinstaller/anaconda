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
import React, { useEffect, useState } from "react";

import {
    Button,
    Flex, FlexItem,
    HelperText, HelperTextItem,
    Label,
    Title,
} from "@patternfly/react-core";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { SyncAltIcon } from "@patternfly/react-icons";

import { ListingTable } from "cockpit-components-table.jsx";

import {
    applyPartitioning,
    createPartitioning,
    getAllDiskSelection,
    getDeviceData,
    getDiskFreeSpace,
    getDiskTotalSpace,
    getUsableDisks,
    partitioningConfigureWithTask,
    resetPartitioning,
    runStorageTask,
    scanDevicesWithTask,
    setInitializationMode,
    setInitializeLabelsEnabled,
    setSelectedDisks,
    setBootloaderDrive,
} from "../../apis/storage.js";

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

const LocalStandardDisks = ({ idPrefix, onAddErrorNotification }) => {
    const [deviceData, setDeviceData] = useState({});
    const [disks, setDisks] = useState({});
    const [refreshCnt, setRefreshCnt] = useState(0);

    useEffect(() => {
        let usableDisks;
        getUsableDisks()
                .then(res => {
                    usableDisks = res[0];
                    return getAllDiskSelection();
                })
                .then(props => {
                    // Select default disks for the partitioning
                    const defaultDisks = selectDefaultDisks({
                        ignoredDisks: props[0].IgnoredDisks.v,
                        selectedDisks: props[0].SelectedDisks.v,
                        usableDisks,
                    });
                    setDisks(usableDisks.reduce((acc, cur) => ({ ...acc, [cur]: defaultDisks.includes(cur) }), {}));

                    // Show disks data
                    usableDisks.forEach(disk => {
                        let deviceData = {};
                        const diskNames = [disk];

                        getDeviceData({ disk })
                                .then(res => {
                                    deviceData = res[0];
                                    return getDiskFreeSpace({ diskNames });
                                }, console.error)
                                .then(free => {
                                    // Since the getDeviceData returns an object with variants as values,
                                    // extend it with variants to keep the format consistent
                                    deviceData.free = cockpit.variant(String, free[0]);
                                    return getDiskTotalSpace({ diskNames });
                                }, console.error)
                                .then(total => {
                                    deviceData.total = cockpit.variant(String, total[0]);
                                    setDeviceData(d => ({ ...d, [disk]: deviceData }));
                                }, console.error);
                    });
                }, console.error);
    }, [refreshCnt]);

    // When the selected disks change in the UI, update in the backend as well
    useEffect(() => {
        const selected = Object.keys(disks).filter(disk => disks[disk]);

        setSelectedDisks({ drives: selected }).catch(onAddErrorNotification);
    }, [disks, onAddErrorNotification]);

    const totalDisksCnt = Object.keys(disks).length;
    const selectedDisksCnt = Object.keys(disks).filter(disk => !!disks[disk]).length;

    if (totalDisksCnt === 0) {
        return <EmptyStatePanel loading />;
    }

    return (
        <>
            <Flex spaceItems={{ default: "spaceItemsLg" }}>
                <Title headingLevel="h3" id={idPrefix + "-local-disks-title"} size="md">
                    {_("Local standard disks")}
                </Title>
                <Label
                  color="blue"
                  id="installation-destination-table-label"
                >
                    {cockpit.format(
                        cockpit.ngettext("$0 (of $1) disk selected", "$0 (of $1) disks selected", selectedDisksCnt),
                        selectedDisksCnt,
                        totalDisksCnt
                    )}
                </Label>
                <FlexItem align={{ default: "alignRight" }}>
                    <Button
                      aria-label={_("Rescan disks")}
                      id={idPrefix + "-rescan-disks"}
                      onClick={() => {
                          scanDevicesWithTask().then(res => {
                              runStorageTask({
                                  task: res[0],
                                  onSuccess: () => resetPartitioning().then(() => setRefreshCnt(refreshCnt + 1), onAddErrorNotification),
                                  onFail: onAddErrorNotification
                              });
                          });
                      }}
                      variant="plain"
                    >
                        <SyncAltIcon />
                    </Button>
                </FlexItem>
            </Flex>
            <ListingTable
              aria-labelledby="installation-destination-local-disk-title"
              {...(totalDisksCnt > 10 && { variant: "compact" })}
              columns={
                  [
                      { title: _("Name"), sortable: totalDisksCnt > 1, header: true },
                      { title: _("ID") },
                      { title: _("Total") },
                      { title: _("Free") },
                  ]
              }
              onSelect={(_, isSelected, diskId) => setDisks({ ...disks, [Object.keys(disks)[diskId]]: isSelected })}
              rows={
                  Object.keys(disks).map(disk => (
                      {
                          selected: !!disks[disk],
                          props: { key: disk, id: disk },
                          columns: [
                              { title: disk },
                              { title: deviceData[disk] && deviceData[disk].description.v },
                              { title: cockpit.format_bytes(deviceData[disk] && deviceData[disk].total.v) },
                              { title: cockpit.format_bytes(deviceData[disk] && deviceData[disk].free.v) },
                          ]
                      }
                  ))
              }
            />
        </>
    );
};

export const InstallationDestination = ({ idPrefix, onAddErrorNotification }) => {
    return (
        <>
            <HelperText>
                <HelperTextItem>{_("Select the device(s) you would like to install to")}</HelperTextItem>
            </HelperText>
            <LocalStandardDisks
              idPrefix={idPrefix}
              onAddErrorNotification={onAddErrorNotification}
            />
        </>
    );
};

export const applyDefaultStorage = ({ onFail, onSuccess }) => {
    let partitioning;
    // CLEAR_PARTITIONS_ALL = 1
    return setInitializationMode({ mode: 1 })
            .then(() => setInitializeLabelsEnabled({ enabled: true }))
            .then(() => setBootloaderDrive({ drive: "" }))
            .then(() => createPartitioning({ method: "AUTOMATIC" }))
            .then(res => {
                partitioning = res[0];
                return partitioningConfigureWithTask({ partitioning });
            })
            .then(tasks => {
                runStorageTask({
                    task: tasks[0],
                    onSuccess: () => (
                        applyPartitioning({ partitioning })
                                .then(onSuccess)
                                .catch(onFail)
                    ),
                    onFail
                });
            })
            .catch(onFail);
};
