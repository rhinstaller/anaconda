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
import React, { useState, useRef, useEffect } from "react";

import {
    Alert,
    Button,
    DataList,
    DataListCell,
    DataListItem,
    DataListItemRow,
    DataListItemCells,
    Drawer,
    DrawerContent,
    DrawerContentBody,
    DrawerActions,
    DrawerHead,
    DrawerPanelContent,
    DrawerCloseButton,
    Flex,
    FlexItem,
    HelperText,
    HelperTextItem,
    Popover,
    PopoverPosition,
    TextContent,
    Title,
    Tooltip,
    Radio,
} from "@patternfly/react-core";

import { HelpIcon } from "@patternfly/react-icons";

import ExclamationTriangleIcon from "@patternfly/react-icons/dist/esm/icons/exclamation-triangle-icon";

import { helpEraseAll, helpUseFreeSpace, helpCustomMountPoint } from "./HelpAutopartOptions.jsx";
import { AnacondaPage } from "../AnacondaPage.jsx";
import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";

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

// TODO unify with HelpDrawer ?
const DetailDrawer = ({ isExpanded, setIsExpanded, detailContent, children }) => {
    const drawerRef = useRef(null);

    const onExpand = () => {
        drawerRef.current && drawerRef.current.focus();
    };

    const onCloseClick = () => {
        setIsExpanded(false);
    };

    const panelConent = (
        <DrawerPanelContent>
            <DrawerHead>
                <span tabIndex={isExpanded ? 0 : -1} ref={drawerRef}>
                    {detailContent}
                </span>
                <DrawerActions>
                    <DrawerCloseButton onClick={onCloseClick} />
                </DrawerActions>
            </DrawerHead>
        </DrawerPanelContent>
    );

    return (
        <Drawer isExpanded={isExpanded} position="right" onExpand={onExpand}>
            <DrawerContent panelContent={panelConent}>
                <DrawerContentBody>{children}</DrawerContentBody>
            </DrawerContent>
        </Drawer>

    );
};

function AvailabilityState (available = true, reason = null, hint = null, shortHint = null) {
    this.available = available;
    this.reason = reason;
    this.hint = hint;
    this.shortHint = shortHint;
}

// TODO total size check could go also to disk selection screen
const checkEraseAll = async (selectedDisks, requiredSize) => {
    const size = await getDiskTotalSpace({ diskNames: selectedDisks }).catch(console.error);
    const availability = new AvailabilityState();
    if (size < requiredSize) {
        availability.available = false;
        availability.reason = _("Not enough space on selected disks.");
        availability.hint = cockpit.format(_(
            "There is not enough space on the disks to install. " +
            "The installation needs $1 of disk space; " +
            "however, the capacity of the selected disks is only $0."
        ), cockpit.format_bytes(size), cockpit.format_bytes(requiredSize));
        availability.shortHint = _("To enable select bigger disks");
    }
    return availability;
};

const checkUseFreeSpace = async (selectedDisks, requiredSize) => {
    const size = await getDiskFreeSpace({ diskNames: selectedDisks }).catch(console.error);
    const availability = new AvailabilityState();
    if (size < requiredSize) {
        availability.available = false;
        availability.reason = _("Not enough free space.");
        availability.hint = cockpit.format(_(
            "There is not enough available free space to install. " +
            "The installation needs $1 of available disk space; " +
            "however, only $0 is currently available on the selected disks."
        ), cockpit.format_bytes(size), cockpit.format_bytes(requiredSize));
        availability.shortHint = _("To enable free up disk space");
    }
    return availability;
};

const checkCustomMountPoint = async (selectedDisks, requiredSize, deviceData) => {
    const availability = new AvailabilityState();

    if (!selectedDisks.some(device => deviceData[device]?.children.v.some(child => deviceData[child]?.type.v === "partition"))) {
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
    screenWarning: _("Erasing the data cannot be undone."),
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
    screenWarning: "",
    dialogTitleIconVariant: "",
    dialogWarningTitle: _("Install on the free space?"),
    dialogWarning: _("The installation will use the available space on your devices and will not erase any device data."),
}, {
    id: "custom-mount-point",
    label: _("Mount point assignment"),
    default: false,
    detail: helpCustomMountPoint,
    check: checkCustomMountPoint,
    // CLEAR_PARTITIONS_NONE = 0
    initializationMode: 0,
    buttonLabel: _("Apply mount point assignment and install"),
    buttonVariant: "danger",
    screenWarning: "",
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

const scenarioDetailContent = (scenario, reason, hint) => {
    return (
        <Flex direction={{ default: "column" }}>
            <Title headingLevel="h3">
                {scenario.label}
            </Title>
            {hint &&
                <Alert
                  id="scenario-disabled-hint"
                  isInline
                  title={reason}
                  variant="warning"
                >
                    {hint}
                </Alert>}
            {scenario.detail}
        </Flex>
    );
};

const predefinedStorageInfo = (
    <Popover
      bodyContent={_(
          "Pre-defined scenarios of the selected disks partitioning."
      )}
      position={PopoverPosition.auto}
    >
        <Button
          variant="link"
          aria-label={_("Pre-defined storage label info")}
          icon={<HelpIcon />}
        />
    </Popover>
);

// TODO add aria items
const GuidedPartitioning = ({ deviceData, selectedDisks, idPrefix, scenarios, storageScenarioId, setStorageScenarioId, setIsFormValid }) => {
    const [selectedScenario, setSelectedScenario] = useState();
    const [scenarioAvailability, setScenarioAvailability] = useState(Object.fromEntries(
        scenarios.map((s) => [s.id, new AvailabilityState()])
    ));
    const [isDetailExpanded, setIsDetailExpanded] = useState(false);
    const [detailContent, setDetailContent] = useState("");

    useEffect(() => {
        const updateScenarioState = async (scenarios) => {
            const requiredSpace = await getRequiredSpace();
            const requiredSize = await getRequiredDeviceSize({ requiredSpace });
            let selectedScenarioId = "";
            let availableScenarioExists = false;
            for await (const scenario of scenarios) {
                const availability = await scenario.check(selectedDisks, requiredSize, deviceData).catch(console.error);
                setScenarioAvailability(ss => ({ ...ss, [scenario.id]: availability }));
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
            setIsFormValid(availableScenarioExists);
        };

        updateScenarioState(scenarios);
    }, [scenarios, deviceData, selectedDisks, setIsFormValid, storageScenarioId]);

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
    }, [scenarios, selectedScenario, setStorageScenarioId]);

    const updateDetailContent = (scenarioId) => {
        const scenario = getScenario(scenarioId);
        const reason = scenarioAvailability[scenarioId].reason;
        const hint = scenarioAvailability[scenarioId].hint;
        setDetailContent(scenarioDetailContent(scenario, reason, hint));
    };

    const onScenarioToggled = (scenarioId) => {
        setSelectedScenario(scenarioId);
        updateDetailContent(scenarioId);
    };

    const showScenarioDetails = (scenarioId) => {
        updateDetailContent(scenarioId);
        setIsDetailExpanded(!isDetailExpanded);
    };

    if (!selectedScenario) {
        return <EmptyStatePanel loading />;
    }

    const scenarioItems = scenarios.map(scenario =>
        <DataListItem key={scenario.id}>
            <DataListItemRow>
                <DataListItemCells dataListCells={[
                    <DataListCell key="radio">
                        {!scenarioAvailability[scenario.id].available &&
                        <Tooltip
                          aria-live="polite"
                          content={scenarioAvailability[scenario.id].shortHint}
                          reference={() => document.getElementById(idPrefix + "-autopart-scenario-" + scenario.id)}
                        />}
                        <Flex direction={{ default: "column" }} spaceItems={{ default: "spaceItemsSm" }}>
                            <FlexItem>
                                <Radio
                                  id={idPrefix + "-autopart-scenario-" + scenario.id}
                                  value={scenario.id}
                                  name="autopart-scenario"
                                  label={scenario.label}
                                  isDisabled={!scenarioAvailability[scenario.id].available}
                                  isChecked={selectedScenario === scenario.id}
                                  onChange={() => onScenarioToggled(scenario.id)}
                                />
                            </FlexItem>
                            {scenarioAvailability[scenario.id].reason &&
                            <FlexItem>
                                <Flex spaceItems={{ default: "spaceItemsLg" }}>
                                    <FlexItem />
                                    <FlexItem>
                                        <HelperText>
                                            <HelperTextItem variant="warning" icon={<ExclamationTriangleIcon />}>
                                                {scenarioAvailability[scenario.id].reason}
                                            </HelperTextItem>
                                        </HelperText>
                                    </FlexItem>
                                </Flex>
                            </FlexItem>}
                        </Flex>
                    </DataListCell>,
                    <DataListCell isFilled={false} key="details">
                        <Button
                          variant="link"
                          isInline
                          onClick={() => showScenarioDetails(scenario.id)}
                        >
                            {_("Learn more")}
                        </Button>
                    </DataListCell>
                ]} />
            </DataListItemRow>
        </DataListItem>
    );

    const GuidedPartitioningList = (
        <DataList>
            {scenarioItems}
        </DataList>
    );

    return (
        <DetailDrawer
          isExpanded={isDetailExpanded}
          setIsExpanded={setIsDetailExpanded}
          detailContent={detailContent}
        >
            <Title headingLevel="h3">
                <Flex spaceItems={{ default: "spaceItemsXs" }}>
                    <FlexItem>{_("Pre-defined storage configurations")}</FlexItem>
                    <FlexItem>{predefinedStorageInfo}</FlexItem>
                </Flex>
            </Title>
            {GuidedPartitioningList}
        </DetailDrawer>
    );
};

export const StorageConfiguration = ({ deviceData, diskSelection, idPrefix, setIsFormValid, storageScenarioId, setStorageScenarioId }) => {
    return (
        <AnacondaPage title={_("Select a storage configuration")}>
            <TextContent>
                {_("Configure the partitioning scheme to be used on the selected disks.")}
            </TextContent>
            <GuidedPartitioning
              deviceData={deviceData}
              selectedDisks={diskSelection.selectedDisks}
              idPrefix={idPrefix}
              scenarios={scenarios}
              setIsFormValid={setIsFormValid}
              storageScenarioId={storageScenarioId}
              setStorageScenarioId={setStorageScenarioId}
            />
        </AnacondaPage>
    );
};
