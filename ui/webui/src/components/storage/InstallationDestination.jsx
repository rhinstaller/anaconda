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
import React, { useEffect, useRef, useState } from "react";

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

import { HelpIcon, LockIcon, LockOpenIcon } from "@patternfly/react-icons";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { ListingTable } from "cockpit-components-table.jsx";

import { helpStorageOptions } from "./HelpStorageOptions.jsx";

import {
    getRequiredDeviceSize,
    resetPartitioning,
    runStorageTask,
    scanDevicesWithTask,
    setSelectedDisks,
} from "../../apis/storage.js";

import {
    getRequiredSpace,
} from "../../apis/payloads";
import { getDevicesAction, getDiskSelectionAction } from "../../actions/storage-actions.js";

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

const containEqualDisks = (disks1, disks2) => {
    const disks1Str = disks1.sort()
            .join();
    const disks2Str = disks2.sort()
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

const LocalStandardDisks = ({ deviceData, diskSelection, dispatch, idPrefix, setIsFormValid, onAddErrorNotification }) => {
    const [isRescanningDisks, setIsRescanningDisks] = useState(false);
    const [equalDisksNotify, setEqualDisksNotify] = useState(false);
    const refUsableDisks = useRef();

    console.debug("LocalStandardDisks: deviceData: ", JSON.stringify(Object.keys(deviceData)), ", diskSelection: ", JSON.stringify(diskSelection));

    useEffect(() => {
        if (isRescanningDisks) {
            refUsableDisks.current = diskSelection.usableDisks;
            setEqualDisksNotify(true);
        }
    }, [isRescanningDisks, diskSelection.usableDisks]);

    useEffect(() => {
        // Select default disks for the partitioning on component mount
        if (refUsableDisks.current !== undefined) {
            return;
        }
        refUsableDisks.current = diskSelection.usableDisks;

        const defaultDisks = selectDefaultDisks({
            ignoredDisks: diskSelection.ignoredDisks,
            selectedDisks: diskSelection.selectedDisks,
            usableDisks: diskSelection.usableDisks,
        });

        if (!containEqualDisks(diskSelection.selectedDisks, defaultDisks)) {
            setSelectedDisks({ drives: defaultDisks });
        }
    }, [diskSelection]);

    const totalDisksCnt = diskSelection.usableDisks.length;
    const selectedDisksCnt = diskSelection.selectedDisks.length;

    useEffect(() => {
        setIsFormValid(selectedDisksCnt > 0);
    }, [selectedDisksCnt, setIsFormValid]);

    const loading = !deviceData || diskSelection.usableDisks.some(disk => !deviceData[disk]);

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
          isDisabled={isRescanningDisks || loading}
          id={idPrefix + "-rescan-disks"}
          variant="secondary"
          onClick={() => {
              setIsRescanningDisks(true);
              setSelectedDisks({ drives: [] });
              scanDevicesWithTask()
                      .then(res => {
                          return runStorageTask({
                              task: res[0],
                              onSuccess: () => resetPartitioning().then(() => {
                                  dispatch(getDevicesAction());
                                  dispatch(getDiskSelectionAction());
                              }, onAddErrorNotification),
                              onFail: onAddErrorNotification
                          });
                      })
                      .finally(() => setIsRescanningDisks(false));
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

    const lockIcon = partition => {
        const isLocked = partition.formatData.attrs.v.has_key?.toLowerCase() !== "true";

        if (isLocked) {
            return <LockIcon />;
        } else {
            return <LockOpenIcon />;
        }
    };

    const expandedContent = (disk) => (
        <ListingTable
          variant="compact"
          columns={[_("Partition"), _("Type"), _("Size")]}
          rows={deviceData[disk]?.children?.v.map(child => {
              const partition = deviceData[child];
              const path = {
                  title: (
                      <Flex spaceItems={{ default: "spaceItemsSm" }}>
                          <FlexItem>{partition.path.v}</FlexItem>
                          {partition.formatData.type.v === "luks" && <FlexItem>{lockIcon(partition)}</FlexItem>}
                      </Flex>
                  )
              };
              const size = { title: cockpit.format_bytes(partition.total.v) };
              const type = { title: partition.formatData.description.v };

              return ({ columns: [path, type, size] });
          })}
        />
    );

    const localDisksRows = diskSelection.usableDisks.map(disk => {
        const hasPartitions = deviceData[disk]?.children?.v.length && deviceData[disk]?.children?.v.every(partition => deviceData[partition]);

        return ({
            selected: !!diskSelection.selectedDisks.includes(disk),
            hasPadding: true,
            props: { key: disk, id: disk },
            columns: [
                { title: disk },
                { title: deviceData[disk] && deviceData[disk].description.v },
                { title: cockpit.format_bytes(deviceData[disk] && deviceData[disk].total.v) },
                { title: cockpit.format_bytes(deviceData[disk] && deviceData[disk].free.v) },
            ],
            ...(hasPartitions && { expandedContent: expandedContent(disk) }),
        });
    });

    const rescanningDisksColumns = localDisksColumns.map(col => ({ ...col, sortable: false }));

    const rescanningDisksRow = (
        [
            {
                props: { colSpan: localDisksColumns.length },
                title: <Skeleton screenreaderText={_("Detecting disks")} />
            }
        ]
    );

    const rescanningDisksRows = diskSelection.usableDisks.map(disk => (
        {
            columns: rescanningDisksRow
        }
    ));

    const dropdownBulkSelect = (
        <DropdownBulkSelect
          onSelectAll={() => setSelectedDisks({ drives: diskSelection.usableDisks })}
          onSelectNone={() => setSelectedDisks({ drives: [] })}
          onChange={(checked) => {
              if (checked) {
                  setSelectedDisks({ drives: diskSelection.usableDisks });
              } else {
                  setSelectedDisks({ drives: [] });
              }
          }}
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
                  ? (_, isSelected, diskId) => {
                      const newDisk = diskSelection.usableDisks[diskId];

                      if (isSelected) {
                          setSelectedDisks({ drives: [...diskSelection.selectedDisks, newDisk] });
                      } else {
                          setSelectedDisks({ drives: diskSelection.selectedDisks.filter(disk => disk !== newDisk) });
                      }
                  }
                  : () => {}
          }
          rows={
              !isRescanningDisks
                  ? localDisksRows
                  : rescanningDisksRows
          }
        />
    );

    const equalDisks = refUsableDisks.current && containEqualDisks(refUsableDisks.current, diskSelection.usableDisks);

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
                    {equalDisksNotify && equalDisks &&
                        <Alert
                          id="no-disks-detected-alert"
                          isInline
                          title={_("No additional disks detected")}
                          variant="info"
                          actionClose={<AlertActionCloseButton onClose={() => { setEqualDisksNotify(false) }} />}
                        />}
                    {localDisksToolbar}
                    {!loading && localDisksTable}
                    {loading && <EmptyStatePanel loading />}
                </FormGroup>
            </FormSection>
        </Form>
    );
};

export const InstallationDestination = ({ deviceData, diskSelection, dispatch, idPrefix, setIsFormValid, onAddErrorNotification, toggleContextHelp, stepNotification, isInProgress }) => {
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
                        "Select the devices to install to. The installation requires " +
                        "$0 of available space. Storage will be automatically partitioned."
                    ), cockpit.format_bytes(requiredSize))}
                    {" "}
                    <Button id="learn-more-about-storage-options" variant="link" isInline onClick={toggleHelpStorageOptions}>
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
              deviceData={deviceData}
              diskSelection={diskSelection}
              dispatch={dispatch}
              idPrefix={idPrefix}
              setIsFormValid={setIsFormValid}
              onAddErrorNotification={onAddErrorNotification}
            />
        </AnacondaPage>
    );
};
