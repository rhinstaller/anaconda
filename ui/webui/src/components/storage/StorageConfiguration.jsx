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
    DataListAction,
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

import { helpEraseAll, helpUseFreeSpace } from "./HelpAutopartOptions.jsx";

import {
    getRequiredDeviceSize,
    getDiskTotalSpace,
    getDiskFreeSpace,
    getSelectedDisks,
    getInitializationMode,
    setInitializationMode,
} from "../../apis/storage.js";

import {
    getRequiredSpace,
} from "../../apis/payloads";

import { AnacondaPage } from "../AnacondaPage.jsx";

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
            "Total size: $0 Required size: $1"
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
        availability.reason = _("Not enough space on selected disks.");
        availability.hint = cockpit.format(_(
            "Free size: $0 Required size: $1"
        ), cockpit.format_bytes(size), cockpit.format_bytes(requiredSize));
        availability.shortHint = _("To enable free up disk space");
    }
    return availability;
};

export const scenarios = [{
    id: "erase-all",
    label: _("Erase devices and install"),
    detail: helpEraseAll,
    check: checkEraseAll,
    default: true,
    // CLEAR_PARTITIONS_ALL = 1
    initializationMode: 1,
}, {
    id: "use-free-space",
    label: _("Use free space for the installation"),
    detail: helpUseFreeSpace,
    check: checkUseFreeSpace,
    default: false,
    // CLEAR_PARTITIONS_NONE = 0
    initializationMode: 0,
}];

const scenarioDetailContent = (scenario, hint) => {
    return (
        <Flex direction={{ default: "column" }}>
            <Title headingLevel="h3">
                {scenario.label}
            </Title>
            {hint &&
                <Alert
                  id="scenario-disabled-hint"
                  isInline
                  title={_("This option is disabled")}
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
// TODO add prefixes to ids (for tests)
const GuidedPartitioning = ({ scenarios, setIsFormValid }) => {
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
            const selectedDisks = await getSelectedDisks();
            const initializationMode = await getInitializationMode();
            let selectedScenarioId = "";
            let availableScenarioExists = false;
            for await (const scenario of scenarios) {
                const availability = await scenario.check(selectedDisks, requiredSize).catch(console.error);
                setScenarioAvailability(ss => ({ ...ss, [scenario.id]: availability }));
                if (availability.available) {
                    availableScenarioExists = true;
                    if (scenario.initializationMode === initializationMode) {
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
    }, [scenarios, setIsFormValid]);

    useEffect(() => {
        const applyScenario = async (scenarioId) => {
            const scenario = scenarios.filter(s => s.id === scenarioId)[0];
            console.log("Updating scenario selected in backend to", scenario.id);
            await setInitializationMode({ mode: scenario.initializationMode }).catch(console.error);
        };
        if (selectedScenario) {
            applyScenario(selectedScenario);
        }
    }, [scenarios, selectedScenario]);

    const updateDetailContent = (scenarioId) => {
        const scenario = scenarios.filter(s => s.id === scenarioId)[0];
        const hint = scenarioAvailability[scenarioId].hint;
        setDetailContent(scenarioDetailContent(scenario, hint));
    };

    const onScenarioToggled = (scenarioId) => {
        setSelectedScenario(scenarioId);
        updateDetailContent(scenarioId);
    };

    const showScenarioDetails = (scenarioId) => {
        updateDetailContent(scenarioId);
        setIsDetailExpanded(!isDetailExpanded);
    };

    const scenarioItems = scenarios.map(scenario =>
        <DataListItem key={scenario.id}>
            <DataListItemRow>
                <DataListItemCells dataListCells={[
                    <DataListAction key="radio">
                        {!scenarioAvailability[scenario.id].available &&
                        <Tooltip
                          aria-live="polite"
                          content={scenarioAvailability[scenario.id].shortHint}
                          reference={() => document.getElementById("autopart-scenario" + scenario.id)}
                        />}
                        <Radio
                          id={"autopart-scenario" + scenario.id}
                          value={scenario.id}
                          name="autopart-scenario"
                          label={scenario.label}
                          isDisabled={!scenarioAvailability[scenario.id].available}
                          isChecked={selectedScenario === scenario.id}
                          onChange={() => onScenarioToggled(scenario.id)}
                        />
                    </DataListAction>,
                    <DataListCell key="more">
                        {scenarioAvailability[scenario.id].reason &&
                        <Flex spaceItems={{ default: "spaceItems2xl" }}>
                            <FlexItem />
                            <FlexItem>
                                <HelperText>
                                    <HelperTextItem variant="warning" icon=<ExclamationTriangleIcon />>
                                        {scenarioAvailability[scenario.id].reason}
                                    </HelperTextItem>
                                </HelperText>
                            </FlexItem>
                            <FlexItem />
                        </Flex>}
                    </DataListCell>,
                    <DataListAction key="details">
                        <Button
                          variant="link"
                          isInline onClick={() => showScenarioDetails(scenario.id)}
                        >
                            {_("Learn more")}
                        </Button>
                    </DataListAction>,
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

export const StorageConfiguration = ({ setIsFormValid }) => {
    return (
        <AnacondaPage title={_("Select a storage configuration")}>
            <TextContent>
                {_("Configure the partitioning scheme to be used on the selected disks.")}
            </TextContent>
            <GuidedPartitioning scenarios={scenarios} setIsFormValid={setIsFormValid} />
        </AnacondaPage>
    );
};
