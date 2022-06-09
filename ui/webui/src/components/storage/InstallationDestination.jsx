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
    Alert,
    Bullseye,
    Button,
    EmptyState,
    EmptyStateIcon,
    Flex,
    FlexItem,
    Form,
    FormGroup,
    Label,
    Spinner,
    Text,
    TextContent,
    TextVariants,
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
    getRequiredDeviceSize,
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

import {
    getRequiredSpace,
} from "../../apis/payloads";

import {
    FormGroupHelpPopover,
    sleep,
} from "../Common.jsx";
import { AnacondaPage } from "../AnacondaPage.jsx";

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
    if (selectedDisks.length) {
        // Do nothing if there are some disks selected
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

const LocalStandardDisks = ({ idPrefix, setIsFormValid, onAddErrorNotification }) => {
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

    const totalDisksCnt = Object.keys(disks).length;
    const selectedDisksCnt = Object.keys(disks).filter(disk => !!disks[disk]).length;

    // When the selected disks change in the UI, update in the backend as well
    useEffect(() => {
        setIsFormValid(selectedDisksCnt > 0);

        const selected = Object.keys(disks).filter(disk => disks[disk]);

        setSelectedDisks({ drives: selected }).catch(onAddErrorNotification);
    }, [disks, onAddErrorNotification, selectedDisksCnt, setIsFormValid]);

    if (totalDisksCnt === 0) {
        return <EmptyStatePanel loading />;
    }

    const localDisksInfo = (
        <FormGroupHelpPopover
          helpContent={_(
              "Locally available storage devices (SATA, NVMe SSD, " +
              "SCSI hard drives, external disks, etc.)"
          )}
        />
    );

    const diskSelectionLabel = (
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
    );

    const rescanDisksButton = (
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
    );

    const localDisksColumns = [
        {
            title: _("Name"),
            sortable: true,
            header: true
        },
        { title: _("ID") },
        { title: _("Total") },
        {
            title: _("Free"),
            props: {
                info: {
                    popover: (
                        <div>{_(
                            "Available storage capacity on the disk."
                        )}
                        </div>
                    ),
                },
            },
        },
    ];

    const localDisksRows = Object.keys(disks).map(disk => (
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
    ));

    return (
        <Form>
            <FormGroup
              label={_("Local standard disks")}
              labelIcon={
                  <Flex display={{ default: "inlineFlex" }}>
                      <FlexItem>{localDisksInfo}</FlexItem>
                      <FlexItem>{diskSelectionLabel}</FlexItem>
                  </Flex>
              }
              labelInfo={rescanDisksButton}
              isRequired
            >
                <ListingTable
                  aria-labelledby="installation-destination-local-disk-title"
                  {...(totalDisksCnt > 10 && { variant: "compact" })}
                  columns={localDisksColumns}
                  onSelect={(_, isSelected, diskId) => setDisks({ ...disks, [Object.keys(disks)[diskId]]: isSelected })}
                  rows={localDisksRows}
                />
            </FormGroup>
        </Form>
    );
};

export const InstallationDestination = ({ idPrefix, setIsFormValid, onAddErrorNotification, stepNotification, isInProgress }) => {
    const [requiredSize, setRequiredSize] = useState(0);

    useEffect(() => {
        getRequiredSpace()
                .then(res => {
                    getRequiredDeviceSize({ requiredSpace: res }).then(res => {
                        setRequiredSize(res);
                    }, console.error);
                }, console.error);
    }, []);

    if (isInProgress) {
        return (
            <Bullseye>
                <EmptyState id="installation-destination-next-spinner">
                    <EmptyStateIcon variant="container" component={Spinner} />
                    <Title size="lg" headingLevel="h4">
                        {_("Checking disks")}
                    </Title>
                    <TextContent>
                        <Text component={TextVariants.p}>
                            {_("This may take a moment")}
                        </Text>
                    </TextContent>
                </EmptyState>
            </Bullseye>
        );
    }

    return (
        <AnacondaPage title={_("Installation destination")}>
            <TextContent>
                <Text component={TextVariants.p}>{
                    cockpit.format(_(
                        "Select the device(s) to install to. The installation requires " +
                        "$0 of available space. Storage will be automatically partitioned."
                    ), cockpit.format_bytes(requiredSize))
                }
                </Text>
            </TextContent>
            {stepNotification && (stepNotification.step === "installation-destination") &&
                <Alert
                  isInline
                  title={stepNotification.message}
                  variant="danger"
                />}
            <Alert
              isInline
              variant="info"
              title={_("Selected disks will be erased at install")}
            >
                <p>
                    {_("To prevent loss, backup the data.")}
                </p>
            </Alert>
            <LocalStandardDisks
              idPrefix={idPrefix}
              setIsFormValid={setIsFormValid}
              onAddErrorNotification={onAddErrorNotification}
            />
        </AnacondaPage>
    );
};

export const applyDefaultStorage = ({ onFail, onSuccess }) => {
    let partitioning;
    // CLEAR_PARTITIONS_ALL = 1
    return setInitializationMode({ mode: 1 })
            .then(() => sleep({ seconds: 2 }))
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
