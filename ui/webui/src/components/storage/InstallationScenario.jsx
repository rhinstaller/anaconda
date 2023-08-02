/*
 * Copyright (C) 2023 Red Hat, Inc.
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
import React, { useState, useEffect } from "react";

import {
    FormGroup,
    Radio,
    Title,
} from "@patternfly/react-core";

import { helpEraseAll, helpUseFreeSpace, helpMountPointMapping } from "./HelpAutopartOptions.jsx";

import {
    getRequiredDeviceSize,
    getDiskTotalSpace,
    getDiskFreeSpace,
    setInitializationMode,
} from "../../apis/storage.js";

import {
    getRequiredSpace,
} from "../../apis/payloads";

const _ = cockpit.gettext;

function AvailabilityState (available = true, reason = null, hint = null, shortHint = null) {
    this.available = available;
    this.reason = reason;
    this.hint = hint;
    this.shortHint = shortHint;
}

const checkEraseAll = ({ requiredSize, diskTotalSpace }) => {
    const availability = new AvailabilityState();
    if (diskTotalSpace < requiredSize) {
        availability.available = false;
        availability.reason = _("Not enough space on selected disks.");
        availability.hint = cockpit.format(_(
            "There is not enough space on the disks to install. " +
            "The installation needs $1 of disk space; " +
            "however, the capacity of the selected disks is only $0."
        ), cockpit.format_bytes(diskTotalSpace), cockpit.format_bytes(requiredSize));
        availability.shortHint = _("To enable select bigger disks");
    }
    return availability;
};

const checkUseFreeSpace = ({ diskFreeSpace, requiredSize }) => {
    const availability = new AvailabilityState();
    if (diskFreeSpace < requiredSize) {
        availability.available = false;
        availability.reason = _("Not enough free space.");
        availability.hint = cockpit.format(_(
            "There is not enough available free space to install. " +
            "The installation needs $1 of available disk space; " +
            "however, only $0 is currently available on the selected disks."
        ), cockpit.format_bytes(diskFreeSpace), cockpit.format_bytes(requiredSize));
        availability.shortHint = _("To enable free up disk space");
    }
    return availability;
};

const checkMountPointMapping = ({ hasPartitions }) => {
    const availability = new AvailabilityState();

    if (!hasPartitions) {
        availability.available = false;
        availability.reason = _("No existing partitions on the selected disks.");
    }
    return availability;
};

const scenarios = [{
    id: "erase-all",
    label: _("Erase data and install"),
    detail: helpEraseAll,
    check: checkEraseAll,
    default: true,
    // CLEAR_PARTITIONS_ALL = 1
    initializationMode: 1,
    buttonLabel: _("Erase data and install"),
    buttonVariant: "danger",
    screenWarning: _("Erasing the data cannot be undone. Be sure to have backups."),
    dialogTitleIconVariant: "warning",
    dialogWarningTitle: _("Erase data and install?"),
    dialogWarning: _("The selected disks will be erased, this cannot be undone. Are you sure you want to continue with the installation?"),
}, {
    id: "use-free-space",
    label: _("Use free space for the installation"),
    detail: helpUseFreeSpace,
    check: checkUseFreeSpace,
    default: false,
    // CLEAR_PARTITIONS_NONE = 0
    initializationMode: 0,
    buttonLabel: _("Install"),
    buttonVariant: "primary",
    screenWarning: _("To prevent loss, make sure to backup your data."),
    dialogTitleIconVariant: "",
    dialogWarningTitle: _("Install on the free space?"),
    dialogWarning: _("The installation will use the available space on your devices and will not erase any device data."),
}, {
    id: "mount-point-mapping",
    label: _("Mount point assignment"),
    default: false,
    detail: helpMountPointMapping,
    check: checkMountPointMapping,
    // CLEAR_PARTITIONS_NONE = 0
    initializationMode: 0,
    buttonLabel: _("Apply mount point assignment and install"),
    buttonVariant: "danger",
    screenWarning: _("To prevent loss, make sure to backup your data."),
    dialogTitleIconVariant: "",
    dialogWarningTitle: _("Install on the custom mount points?"),
    dialogWarning: _("The installation will use your configured partitioning layout."),
}];

export const getScenario = (scenarioId) => {
    return scenarios.filter(s => s.id === scenarioId)[0];
};

export const scenarioForInitializationMode = (mode) => {
    const ss = scenarios.filter(s => s.initializationMode === mode);
    if (ss.length > 0) {
        return ss[0];
    }
};

export const getDefaultScenario = () => {
    return scenarios.filter(s => s.default)[0];
};

const InstallationScenarioSelector = ({ deviceData, selectedDisks, idPrefix, storageScenarioId, setStorageScenarioId, setIsFormValid }) => {
    const [selectedScenario, setSelectedScenario] = useState();
    const [scenarioAvailability, setScenarioAvailability] = useState(Object.fromEntries(
        scenarios.map((s) => [s.id, new AvailabilityState()])
    ));
    const [requiredSize, setRequiredSize] = useState();
    const [diskTotalSpace, setDiskTotalSpace] = useState();
    const [diskFreeSpace, setDiskFreeSpace] = useState();
    const [hasPartitions, setHasPartitions] = useState();

    useEffect(() => {
        const updateSizes = async () => {
            const diskTotalSpace = await getDiskTotalSpace({ diskNames: selectedDisks }).catch(console.error);
            const diskFreeSpace = await getDiskFreeSpace({ diskNames: selectedDisks }).catch(console.error);

            setDiskTotalSpace(diskTotalSpace);
            setDiskFreeSpace(diskFreeSpace);
        };
        updateSizes();
    }, [selectedDisks]);

    useEffect(() => {
        const updateRequiredSize = async () => {
            const requiredSpace = await getRequiredSpace().catch(console.error);
            const requiredSize = await getRequiredDeviceSize({ requiredSpace }).catch(console.error);

            setRequiredSize(requiredSize);
        };
        updateRequiredSize();
    }, []);

    useEffect(() => {
        const hasPartitions = selectedDisks.some(device => deviceData[device]?.children.v.some(child => deviceData[child]?.type.v === "partition"));

        setHasPartitions(hasPartitions);
    }, [selectedDisks, deviceData]);

    useEffect(() => {
        let selectedScenarioId = "";
        let availableScenarioExists = false;

        if (requiredSize === undefined) {
            return;
        }

        const newAvailability = {};
        for (const scenario of scenarios) {
            const availability = scenario.check({ diskTotalSpace, diskFreeSpace, hasPartitions, requiredSize });
            newAvailability[scenario.id] = availability;
            if (availability.available) {
                availableScenarioExists = true;
                if (scenario.id === storageScenarioId) {
                    console.log(`Selecting backend scenario ${scenario.id}`);
                    selectedScenarioId = scenario.id;
                }
                if (!selectedScenarioId && scenario.default) {
                    console.log(`Selecting default scenario ${scenario.id}`);
                    selectedScenarioId = scenario.id;
                }
            }
        }
        setSelectedScenario(selectedScenarioId);
        setScenarioAvailability(newAvailability);
        setIsFormValid(availableScenarioExists);
    }, [deviceData, hasPartitions, requiredSize, diskFreeSpace, diskTotalSpace, setIsFormValid, storageScenarioId]);

    useEffect(() => {
        const applyScenario = async (scenarioId) => {
            const scenario = getScenario(scenarioId);
            setStorageScenarioId(scenarioId);
            console.log("Updating scenario selected in backend to", scenario.id);

            await setInitializationMode({ mode: scenario.initializationMode }).catch(console.error);
        };
        if (selectedScenario) {
            applyScenario(selectedScenario);
        }
    }, [selectedScenario, setStorageScenarioId]);

    const onScenarioToggled = (scenarioId) => {
        setSelectedScenario(scenarioId);
    };

    const scenarioItems = scenarios.map(scenario => (
        <Radio
          className={idPrefix + "-scenario"}
          key={scenario.id}
          id={idPrefix + "-scenario-" + scenario.id}
          value={scenario.id}
          name={idPrefix + "-scenario"}
          label={scenario.label}
          isDisabled={!scenarioAvailability[scenario.id].available}
          isChecked={storageScenarioId === scenario.id}
          onChange={() => onScenarioToggled(scenario.id)}
          description={scenario.detail}
          body={
              <>
                  {selectedDisks.length > 0 && scenarioAvailability[scenario.id].reason &&
                  <span className={idPrefix + "-scenario-disabled-reason"}>
                      {scenarioAvailability[scenario.id].reason}
                  </span>}
                  {selectedDisks.length > 0 && <span className={idPrefix + "-scenario-disabled-shorthint"}>{scenarioAvailability[scenario.id].shortHint}</span>}
              </>
          } />
    ));

    return scenarioItems;
};

export const InstallationScenario = ({ deviceData, diskSelection, idPrefix, setIsFormValid, storageScenarioId, setStorageScenarioId, isBootIso }) => {
    const headingLevel = isBootIso ? "h2" : "h3";

    return (
        <>
            <Title headingLevel={headingLevel}>{_("How would you like to install?")}</Title>
            <FormGroup isStack hasNoPaddingTop>
                <InstallationScenarioSelector
                  deviceData={deviceData}
                  selectedDisks={diskSelection.selectedDisks}
                  idPrefix={idPrefix}
                  setIsFormValid={setIsFormValid}
                  storageScenarioId={storageScenarioId}
                  setStorageScenarioId={setStorageScenarioId}
                />
            </FormGroup>
        </>
    );
};
