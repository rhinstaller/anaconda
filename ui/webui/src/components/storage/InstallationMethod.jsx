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
    Flex,
    FlexItem,
    Form,
    FormGroup,
    Select,
    SelectOption,
    SelectVariant,
    Title,
} from "@patternfly/react-core";
import { SyncAltIcon } from "@patternfly/react-icons";

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

const InstallationDestination = ({ deviceData, diskSelection, dispatch, idPrefix, isBootIso, setIsFormValid, onAddErrorNotification }) => {
    const [isRescanningDisks, setIsRescanningDisks] = useState(false);
    const [equalDisksNotify, setEqualDisksNotify] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
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

    const rescanDisksButton = (
        <Button
          aria-label={_("Re-scan")}
          isDisabled={isRescanningDisks || loading}
          isInline
          id={idPrefix + "-rescan-disks"}
          variant="link"
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
                                      .catch(onAddErrorNotification),
                              onFail: onAddErrorNotification
                          });
                      })
                      .finally(() => setIsRescanningDisks(false));
          }}
        >
            {_("Rescan")}
        </Button>
    );

    const onSelect = (event, selection) => {
        const selectedDisk = selection.name;

        if (diskSelection.selectedDisks.includes(selectedDisk)) {
            setSelectedDisks({ drives: diskSelection.selectedDisks.filter(disk => disk !== selectedDisk) });
        } else {
            setSelectedDisks({ drives: [...diskSelection.selectedDisks, selectedDisk] });
        }
    };

    const clearSelection = () => {
        setSelectedDisks({ drives: [] });
    };

    const localDisksSelect = (
        <Select
          toggleId={idPrefix + "-disk-selector-toggle"}
          aria-labelledby={idPrefix + "-disk-selector-title"}
          variant={SelectVariant.typeaheadMulti}
          onToggle={() => setIsOpen(!isOpen)}
          onSelect={onSelect}
          onClear={clearSelection}
          selections={diskSelection.selectedDisks.map(disk => ({
              toString: function () {
                  return `${this.description} (${this.name})`;
              },
              name: disk,
              description: deviceData[disk]?.description.v,
              compareTo: function (value) {
                  return this.toString()
                          .toLowerCase()
                          .includes(value.toString().toLowerCase());
              }
          }))}
          isOpen={isOpen}
          placeholderText={_("Select a disk")}
        >
            {diskSelection.usableDisks.map(disk => (
                <SelectOption
                  id={idPrefix + "-disk-selector-option-" + disk}
                  key={disk}
                  value={{
                      toString: function () {
                          return `${this.description} (${this.name})`;
                      },
                      name: disk,
                      description: deviceData[disk]?.description.v,
                      compareTo: function (value) {
                          return this.toString()
                                  .toLowerCase()
                                  .includes(value.toString().toLowerCase());
                      }
                  }}
                  description={cockpit.format_bytes(deviceData[disk]?.total.v)}
                />
            ))}
        </Select>
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
                </Flex>
            </FormGroup>
        </>
    );
};

export const InstallationMethod = ({
    deviceData,
    diskSelection,
    dispatch,
    idPrefix,
    isBootIso,
    isInProgress,
    onAddErrorNotification,
    osRelease,
    setIsFormValid,
    setStorageScenarioId,
    stepNotification,
    storageScenarioId,
}) => {
    return (
        <AnacondaPage title={!isBootIso ? cockpit.format(_("Welcome. Let's install $0 now."), osRelease.REDHAT_SUPPORT_PRODUCT) : null}>
            <Form className={idPrefix + "-selector"} id={idPrefix + "-selector-form"}>
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
                  onAddErrorNotification={onAddErrorNotification}
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
