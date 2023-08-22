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
    Chip,
    ChipGroup,
    Flex,
    FlexItem,
    Form,
    FormGroup,
    MenuToggle,
    Select,
    SelectList,
    SelectOption,
    Spinner,
    TextInputGroup,
    TextInputGroupMain,
    TextInputGroupUtilities,
    Title,
} from "@patternfly/react-core";
import { SyncAltIcon, TimesIcon, WrenchIcon } from "@patternfly/react-icons";

import { InstallationScenario } from "./InstallationScenario.jsx";

import {
    resetPartitioning,
    runStorageTask,
    scanDevicesWithTask,
    setSelectedDisks,
} from "../../apis/storage.js";

import { getDevicesAction, getDiskSelectionAction } from "../../actions/storage-actions.js";
import { AnacondaPage } from "../AnacondaPage.jsx";
import { debug } from "../../helpers/log.js";

import "./InstallationMethod.scss";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

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

const LocalDisksSelect = ({ deviceData, diskSelection, idPrefix, isRescanningDisks, setSelectedDisks }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState("");
    const [focusedItemIndex, setFocusedItemIndex] = useState(null);
    const [diskSelectionInProgress, setDiskSelectionInProgress] = useState(false);
    const textInputRef = useRef();

    useEffect(() => {
        setDiskSelectionInProgress(false);
    }, [diskSelection.selectedDisks]);

    let selectOptions = diskSelection.usableDisks
            .map(disk => ({
                description: deviceData[disk]?.description.v,
                name: disk,
                size: cockpit.format_bytes(deviceData[disk]?.total.v),
                value: disk,
            }))
            .filter(option =>
                String(option.name)
                        .toLowerCase()
                        .includes(inputValue.toLowerCase()) ||
                String(option.description)
                        .toLowerCase()
                        .includes(inputValue.toLowerCase())
            );

    if (selectOptions.length === 0) {
        selectOptions = [
            { children: _("No results found"), value: "no results" }
        ];
    }

    const onSelect = (selectedDisk) => {
        setDiskSelectionInProgress(true);

        if (diskSelection.selectedDisks.includes(selectedDisk)) {
            setSelectedDisks({ drives: diskSelection.selectedDisks.filter(disk => disk !== selectedDisk) });
        } else {
            setSelectedDisks({ drives: [...diskSelection.selectedDisks, selectedDisk] });
        }
        textInputRef.current?.focus();
        setIsOpen(false);
    };

    const clearSelection = () => {
        setSelectedDisks({ drives: [] });
    };

    const handleMenuArrowKeys = (key) => {
        let indexToFocus;

        if (isOpen) {
            if (key === "ArrowUp") {
                // When no index is set or at the first index, focus to the last, otherwise decrement focus index
                if (focusedItemIndex === null || focusedItemIndex === 0) {
                    indexToFocus = selectOptions.length - 1;
                } else {
                    indexToFocus = focusedItemIndex - 1;
                }
            }

            if (key === "ArrowDown") {
                // When no index is set or at the last index, focus to the first, otherwise increment focus index
                if (focusedItemIndex === null || focusedItemIndex === selectOptions.length - 1) {
                    indexToFocus = 0;
                } else {
                    indexToFocus = focusedItemIndex + 1;
                }
            }

            setFocusedItemIndex(indexToFocus);
        }
    };

    const onInputKeyDown = (event) => {
        const enabledMenuItems = selectOptions.filter((menuItem) => !menuItem.isDisabled);
        const [firstMenuItem] = enabledMenuItems;
        const focusedItem = focusedItemIndex ? enabledMenuItems[focusedItemIndex] : firstMenuItem;

        switch (event.key) {
        // Select the first available option
        case "Enter":
            if (!isOpen) {
                setIsOpen((prevIsOpen) => !prevIsOpen);
            } else if (focusedItem.name !== "no results") {
                onSelect(focusedItem.name);
            }
            break;
        case "Tab":
        case "Escape":
            setIsOpen(false);
            break;
        case "ArrowUp":
        case "ArrowDown":
            event.preventDefault();
            handleMenuArrowKeys(event.key);
            break;
        }
    };

    const onToggleClick = () => {
        setIsOpen(!isOpen);
    };

    const onTextInputChange = (_event, value) => {
        setInputValue(value);
    };

    const toggle = (toggleRef) => (
        <MenuToggle
          id={idPrefix + "-toggle"}
          variant="typeahead"
          onClick={onToggleClick}
          innerRef={toggleRef}
          isExpanded={isOpen}
          isDisabled={diskSelectionInProgress || isRescanningDisks}
          className={idPrefix}
        >
            <TextInputGroup isPlain>
                <TextInputGroupMain
                  value={inputValue}
                  onClick={onToggleClick}
                  onChange={onTextInputChange}
                  onKeyDown={onInputKeyDown}
                  autoComplete="off"
                  innerRef={textInputRef}
                  placeholder={!diskSelectionInProgress ? _("Select a disk") : _("Applying new disk selection...")}
                  role="combobox"
                  isExpanded={isOpen}
                >
                    <ChipGroup aria-label={_("Current selections")}>
                        {diskSelection.selectedDisks.map((selection, index) => (
                            <Chip
                              key={index}
                              onClick={(ev) => {
                                  ev.stopPropagation();
                                  onSelect(selection);
                              }}
                            >
                                {selection}
                            </Chip>
                        ))}
                    </ChipGroup>
                </TextInputGroupMain>
                <TextInputGroupUtilities>
                    {diskSelection.selectedDisks.length > 0 && (
                        <Button
                          aria-label={_("Clear input value")}
                          id={idPrefix + "-clear"}
                          variant="plain"
                          onClick={() => {
                              setInputValue("");
                              clearSelection();
                              textInputRef?.current?.focus();
                          }}
                        >
                            <TimesIcon aria-hidden />
                        </Button>
                    )}
                    {diskSelectionInProgress && <Spinner size="lg" />}
                </TextInputGroupUtilities>
            </TextInputGroup>
        </MenuToggle>
    );

    return (
        <Select
          aria-labelledby={idPrefix + "-title"}
          isOpen={isOpen}
          onOpenChange={() => setIsOpen(false)}
          onSelect={(ev, selection) => onSelect(selection)}
          selected={diskSelection.selectedDisks}
          toggle={toggle}
        >
            <SelectList isAriaMultiselectable>
                {selectOptions.map((option, index) => (
                    <SelectOption
                      isDisabled={option.value === "no results"}
                      description={option.size}
                      id={idPrefix + "-option-" + option.name}
                      isFocused={focusedItemIndex === index}
                      key={option.value}
                      value={option.value}
                    >
                        {
                            option.name
                                ? cockpit.format("$0 ($1)", option.name, option.description)
                                : option.children
                        }
                    </SelectOption>
                ))}
            </SelectList>
        </Select>
    );
};

const InstallationDestination = ({ deviceData, diskSelection, dispatch, idPrefix, isBootIso, setIsFormValid, onCritFail }) => {
    const [isRescanningDisks, setIsRescanningDisks] = useState(false);
    const [equalDisksNotify, setEqualDisksNotify] = useState(false);
    const refUsableDisks = useRef();

    debug("DiskSelector: deviceData: ", JSON.stringify(Object.keys(deviceData)), ", diskSelection: ", JSON.stringify(diskSelection));

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

    const selectedDisksCnt = diskSelection.selectedDisks.length;

    useEffect(() => {
        setIsFormValid(selectedDisksCnt > 0);
    }, [selectedDisksCnt, setIsFormValid]);

    const loading = !deviceData || diskSelection.usableDisks.some(disk => !deviceData[disk]);

    const errorHandler = onCritFail({
        context: N_("Rescanning of the disks failed.")
    });

    const rescanDisksButton = (
        <Button
          aria-label={_("Re-scan")}
          isDisabled={isRescanningDisks || loading}
          isInline
          id={idPrefix + "-rescan-disks"}
          variant="link"
          isLoading={isRescanningDisks}
          icon={<SyncAltIcon />}
          onClick={() => {
              setIsRescanningDisks(true);
              setSelectedDisks({ drives: [] });
              scanDevicesWithTask()
                      .then(res => {
                          return runStorageTask({
                              task: res[0],
                              onSuccess: () => resetPartitioning()
                                      .then(() => Promise.all([
                                          dispatch(getDevicesAction()),
                                          dispatch(getDiskSelectionAction())
                                      ]))
                                      .catch(errorHandler),
                              onFail: errorHandler
                          });
                      })
                      .finally(() => setIsRescanningDisks(false));
          }}
        >
            {_("Rescan")}
        </Button>
    );

    const localDisksSelect = (
        <LocalDisksSelect
          idPrefix={idPrefix + "-disk-selector"}
          deviceData={deviceData}
          diskSelection={diskSelection}
          setSelectedDisks={setSelectedDisks}
          isRescanningDisks={isRescanningDisks}
        />
    );

    const equalDisks = refUsableDisks.current && containEqualDisks(refUsableDisks.current, diskSelection.usableDisks);
    const headingLevel = isBootIso ? "h2" : "h3";

    return (
        <>
            <Title headingLevel={headingLevel} id={idPrefix + "-disk-selector-title"}>{_("Destination")}</Title>
            {equalDisksNotify && equalDisks &&
                <Alert
                  id="no-disks-detected-alert"
                  isInline
                  title={_("No additional disks detected")}
                  variant="info"
                  actionClose={<AlertActionCloseButton onClose={() => { setEqualDisksNotify(false) }} />}
                />}
            <FormGroup>
                <Flex spaceItems={{ default: "spaceItemsMd" }} alignItems={{ default: "alignItemsCenter" }}>
                    {(diskSelection.usableDisks.length > 1 || (diskSelection.usableDisks.length === 1 && diskSelection.selectedDisks.length === 0))
                        ? localDisksSelect
                        : (
                            diskSelection.usableDisks.length === 1 && diskSelection.selectedDisks.length === 1
                                ? (
                                    <Flex id={idPrefix + "-target-disk"}>
                                        <FlexItem>
                                            {cockpit.format(
                                                _("Installing to $0 ($1)"),
                                                deviceData[diskSelection.selectedDisks[0]]?.description.v,
                                                diskSelection.selectedDisks[0]
                                            )}
                                        </FlexItem>
                                        <FlexItem className={idPrefix + "-target-disk-size"}>
                                            {cockpit.format_bytes(deviceData[diskSelection.selectedDisks[0]]?.total.v)}
                                        </FlexItem>
                                    </Flex>
                                )
                                : _("No usable disks detected")
                        )}
                    {rescanDisksButton}
                    <ModifyStorageButton isBootIso={isBootIso} />
                </Flex>
            </FormGroup>
        </>
    );
};

const ModifyStorageButton = ({ isBootIso }) => {
    if (isBootIso) {
        return null;
    }

    return (
        <Button variant="link" icon={<WrenchIcon />} onClick={() => cockpit.spawn(["blivet-gui"])}>
            {_("Modify storage")}
        </Button>
    );
};

export const InstallationMethod = ({
    deviceData,
    diskSelection,
    dispatch,
    idPrefix,
    isBootIso,
    isInProgress,
    onCritFail,
    osRelease,
    setIsFormValid,
    setStorageScenarioId,
    stepNotification,
    storageScenarioId,
}) => {
    return (
        <AnacondaPage title={!isBootIso ? cockpit.format(_("Welcome. Let's install $0 now."), osRelease.REDHAT_SUPPORT_PRODUCT) : null}>
            <Form
              className={idPrefix + "-selector"}
              id={idPrefix + "-selector-form"}
              onSubmit={e => { e.preventDefault(); return false }}
            >
                {stepNotification && (stepNotification.step === "installation-method") &&
                    <Alert
                      isInline
                      title={stepNotification.message}
                      variant="danger"
                    />}
                <InstallationDestination
                  deviceData={deviceData}
                  diskSelection={diskSelection}
                  dispatch={dispatch}
                  idPrefix={idPrefix}
                  isBootIso={isBootIso}
                  setIsFormValid={setIsFormValid}
                  onCritFail={onCritFail}
                />
                <InstallationScenario
                  deviceData={deviceData}
                  diskSelection={diskSelection}
                  dispatch={dispatch}
                  idPrefix={idPrefix}
                  isBootIso={isBootIso}
                  setIsFormValid={setIsFormValid}
                  setStorageScenarioId={setStorageScenarioId}
                  storageScenarioId={storageScenarioId}
                />
            </Form>
        </AnacondaPage>
    );
};
