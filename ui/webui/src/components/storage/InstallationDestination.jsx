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
    AlertActionCloseButton,
    Button,
    Divider,
    Dropdown,
    DropdownItem,
    DropdownToggle,
    DropdownToggleCheckbox,
    Flex,
    FlexItem,
    Form,
    FormGroup,
    FormSection,
    Popover,
    PopoverPosition,
    Skeleton,
    Text,
    TextContent,
    TextVariants,
    Toolbar,
    ToolbarContent,
    ToolbarItem,
    Tooltip,
} from "@patternfly/react-core";

import { HelpIcon } from "@patternfly/react-icons";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { ListingTable } from "cockpit-components-table.jsx";

import { helpStorageOptions } from "./HelpStorageOptions.jsx";

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
    setInitializeLabelsEnabled,
    setSelectedDisks,
    setBootloaderDrive,
} from "../../apis/storage.js";

import {
    getRequiredSpace,
} from "../../apis/payloads";

import {
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
        console.log("Selecting disks selected in backend:", selectedDisks.join(","));
        return selectedDisks;
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

const setSelectionForAllDisks = ({ disks, value }) => {
    return (Object.keys(disks).reduce((acc, cur) => ({ ...acc, [cur]: value }), {}));
};

const containEqualDisks = (disks1, disks2) => {
    const disks1Str = Object.keys(disks1).sort()
            .join();
    const disks2Str = Object.keys(disks2).sort()
            .join();
    return disks1Str === disks2Str;
};

const DropdownBulkSelect = ({
    onSelectAll,
    onSelectNone,
    onChange,
    selectedCnt,
    totalCnt,
    isDisabled
}) => {
    const [isOpen, setIsOpen] = React.useState(false);

    const onToggle = (isOpen) => {
        setIsOpen(isOpen);
    };

    const onFocus = () => {
        const element = document.getElementById("local-disks-bulk-select-toggle");
        element.focus();
    };

    const onSelect = () => {
        setIsOpen(false);
        onFocus();
    };

    const dropdownItems = [
        <DropdownItem
          key="select-none"
          component="button"
          aria-label={_("Select no disk")}
          onClick={onSelectNone}
          id="local-disks-bulk-select-none"
        >
            {_("Select none")}
        </DropdownItem>,
        <DropdownItem
          key="select-all"
          component="button"
          aria-label={_("Select all disks")}
          onClick={onSelectAll}
          id="local-disks-bulk-select-all"
        >
            {_("Select all")}
        </DropdownItem>,
    ];

    const splitButtonItems = [
        <DropdownToggleCheckbox
          key="select-multiple-split-checkbox"
          id="select-multiple-split-checkbox"
          aria-label={_("Select multiple disks")}
          isChecked={selectedCnt > 0 ? (selectedCnt === totalCnt ? true : null) : false}
          onChange={onChange}
        >
            {selectedCnt > 0 ? cockpit.format(cockpit.ngettext("$0 selected", "$0 selected", selectedCnt), selectedCnt) : ""}
        </DropdownToggleCheckbox>,
    ];

    return (
        <Dropdown
          onSelect={onSelect}
          toggle={
              <DropdownToggle
                splitButtonItems={splitButtonItems}
                onToggle={onToggle}
                id="local-disks-bulk-select-toggle"
                isDisabled={isDisabled}
              />
          }
          isOpen={isOpen}
          dropdownItems={dropdownItems}
        />
    );
};

const LocalStandardDisks = ({ idPrefix, setIsFormValid, onAddErrorNotification }) => {
    const [deviceData, setDeviceData] = useState({});
    const [disks, setDisks] = useState({});
    const [refreshCnt, setRefreshCnt] = useState(0);
    const [isRescanningDisks, setIsRescanningDisks] = useState(false);
    const [lastRescanDisks, setLastRescanDisks] = useState({});
    const [equalDisksNotify, setEqualDisksNotify] = useState(false);

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
        // Do not update on the inital value, wait for initialization by the other effect
        if (Object.keys(disks).length === 0) {
            return;
        }
        setIsFormValid(selectedDisksCnt > 0);

        const selected = Object.keys(disks).filter(disk => disks[disk]);
        console.log("Updating storage backend with selected disks:", selected.join(","));

        setSelectedDisks({ drives: selected }).catch(onAddErrorNotification);
    }, [disks, onAddErrorNotification, selectedDisksCnt, setIsFormValid]);

    if (totalDisksCnt === 0) {
        return <EmptyStatePanel loading />;
    }

    const localDisksInfo = (
        <Popover
          bodyContent={_(
              "Locally available storage devices (SATA, NVMe SSD, " +
              "SCSI hard drives, external disks, etc.)"
          )}
          position={PopoverPosition.auto}
        >
            <Button
              variant="link"
              aria-label={_("Local disks label info")}
              icon={<HelpIcon />}
            />
        </Popover>
    );

    const rescanDisksButton = (
        <Button
          aria-label={_("Detect disks")}
          id={idPrefix + "-rescan-disks"}
          variant="secondary"
          onClick={() => {
              setIsRescanningDisks(true);
              setLastRescanDisks({ ...disks });
              setDisks(setSelectionForAllDisks({ disks, value: false }));
              scanDevicesWithTask()
                      .then(res => {
                          runStorageTask({
                              task: res[0],
                              onSuccess: () => resetPartitioning().then(() => setRefreshCnt(refreshCnt + 1), onAddErrorNotification),
                              onFail: onAddErrorNotification
                          });
                      })
                      .finally(() => { setIsRescanningDisks(false); setEqualDisksNotify(true) });
          }}
        >
            <Tooltip
              content={
                  <div>
                      {_("Scans for local storage devices")}
                  </div>
              }
              reference={() => document.getElementById(idPrefix + "-rescan-disks")}
            />
            {_("Detect disks")}
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

    const rescanningDisksColumns = localDisksColumns.map(col => ({ ...col, sortable: false }));

    const rescanningDisksRow = (
        [
            {
                props: { colSpan: localDisksColumns.length },
                title: <Skeleton screenreaderText={_("Detecting disks")} />
            }
        ]
    );

    const rescanningDisksRows = Object.keys(disks).map(disk => (
        {
            columns: rescanningDisksRow
        }
    ));

    const dropdownBulkSelect = (
        <DropdownBulkSelect
          onSelectAll={() => setDisks(setSelectionForAllDisks({ disks, value: true }))}
          onSelectNone={() => setDisks(setSelectionForAllDisks({ disks, value: false }))}
          onChange={(checked) => setDisks(setSelectionForAllDisks({ disks, value: checked }))}
          selectedCnt={selectedDisksCnt}
          totalCnt={totalDisksCnt}
          isDisabled={isRescanningDisks}
        />

    );

    const localDisksToolbar = (
        <Toolbar>
            <ToolbarContent>
                <ToolbarItem variant="bulk-select">
                    {dropdownBulkSelect}
                </ToolbarItem>
                <ToolbarItem variant="separator">
                    <Divider orientation={{ default: "vertical" }} />
                </ToolbarItem>
                <ToolbarItem>
                    {rescanDisksButton}
                </ToolbarItem>
            </ToolbarContent>
        </Toolbar>
    );

    const localDisksTable = (
        <ListingTable
          aria-labelledby="installation-destination-local-disk-title"
          {...(totalDisksCnt > 10 && { variant: "compact" })}
          columns={
              !isRescanningDisks
                  ? localDisksColumns
                  : rescanningDisksColumns
          }
          onSelect={
              !isRescanningDisks
                  ? (_, isSelected, diskId) => setDisks({ ...disks, [Object.keys(disks)[diskId]]: isSelected })
                  : () => {}
          }
          rows={
              !isRescanningDisks
                  ? localDisksRows
                  : rescanningDisksRows
          }
        />
    );

    return (
        <Form>
            <FormSection
              title={
                  <Flex spaceItems={{ default: "spaceItemsXs" }}>
                      <FlexItem><h3>{_("Local standard disks")}</h3></FlexItem>
                      <FlexItem>{localDisksInfo}</FlexItem>
                  </Flex>
              }
            >
                <FormGroup>
                    {equalDisksNotify && containEqualDisks(disks, lastRescanDisks) &&
                        <Alert
                          id="no-disks-detected-alert"
                          isInline
                          title={_("No additional disks detected")}
                          variant="info"
                          actionClose=<AlertActionCloseButton onClose={() => setEqualDisksNotify(false)} />
                        />}
                    {localDisksToolbar}
                    {localDisksTable}
                </FormGroup>
            </FormSection>
        </Form>
    );
};

export const InstallationDestination = ({ idPrefix, setIsFormValid, onAddErrorNotification, toggleContextHelp, stepNotification, isInProgress }) => {
    const [requiredSize, setRequiredSize] = useState(0);

    const toggleHelpStorageOptions = () => {
        toggleContextHelp(helpStorageOptions);
    };

    useEffect(() => {
        getRequiredSpace()
                .then(res => {
                    getRequiredDeviceSize({ requiredSpace: res }).then(res => {
                        setRequiredSize(res);
                    }, console.error);
                }, console.error);
    }, []);

    return (
        <AnacondaPage title={_("Select storage devices")}>
            <TextContent>
                <Text id={idPrefix + "-hint"} component={TextVariants.p}>
                    {cockpit.format(_(
                        "Select the device(s) to install to. The installation requires " +
                        "$0 of available space. Storage will be automatically partitioned."
                    ), cockpit.format_bytes(requiredSize))}
                    {" "}
                    <Button variant="link" isInline onClick={toggleHelpStorageOptions}>
                        {_("Learn more about your storage options.")}
                    </Button>
                </Text>

            </TextContent>
            {stepNotification && (stepNotification.step === "installation-destination") &&
                <Alert
                  isInline
                  title={stepNotification.message}
                  variant="danger"
                />}
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
    return sleep({ seconds: 2 })
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
