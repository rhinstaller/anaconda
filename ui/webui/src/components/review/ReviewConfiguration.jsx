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
    Title,
    DataList, DataListItem,
    DataListItemRow, DataListItemCells,
    DataListCell,
    DescriptionList, DescriptionListGroup,
    DescriptionListTerm, DescriptionListDescription,
    ExpandableSection,
    Modal, ModalVariant,
    Alert
} from "@patternfly/react-core";

import {
    getSelectedDisks,
    getDeviceData,
    getAppliedPartitioning,
    getPartitioningRequest,
    getInitializationMode,
} from "../../apis/storage.js";

import {
    getLanguage, getLanguageData,
} from "../../apis/localization.js";
import { AnacondaPage } from "../AnacondaPage.jsx";

import { scenarioForInitializationMode, getScenario } from "../storage/StorageConfiguration.jsx";

const _ = cockpit.gettext;

export const ReviewDescriptionList = ({ children }) => {
    return (
        <DescriptionList
          isHorizontal
          horizontalTermWidthModifier={{
              default: "12ch",
              sm: "15ch",
              md: "20ch",
              lg: "20ch",
              xl: "20ch",
              "2xl": "20ch",
          }}
        >
            {children}
        </DescriptionList>
    );
};

export const ReviewConfiguration = ({ idPrefix, setStorageScenarioId }) => {
    const [deviceData, setDeviceData] = useState({});
    const [selectedDisks, setSelectedDisks] = useState();
    const [systemLanguage, setSystemLanguage] = useState();
    const [disksExpanded, setDisksExpanded] = useState();
    const [encrypt, setEncrypt] = useState();
    const [storageScenario, setStorageScenario] = useState();

    useEffect(() => {
        const initializeLanguage = async () => {
            const lang = await getLanguage().catch(console.error);
            const langData = await getLanguageData({ lang }).catch(console.error);
            setSystemLanguage(langData["native-name"].v);
        };
        const initializeDisks = async () => {
            const selDisks = await getSelectedDisks().catch(console.error);
            setDisksExpanded(selDisks.length < 2);
            setSelectedDisks(selDisks);
            for (const disk of selDisks) {
                const devData = await getDeviceData({ disk }).catch(console.error);
                setDeviceData(d => ({ ...d, [disk]: devData[0] }));
            }
        };
        const initializeEncrypt = async () => {
            const partitioning = await getAppliedPartitioning().catch(console.error);
            const request = await getPartitioningRequest({ partitioning }).catch(console.error);
            setEncrypt(request.encrypted.v);
        };
        const initializeScenario = async () => {
            const mode = await getInitializationMode().catch(console.error);
            setStorageScenario(scenarioForInitializationMode(mode).id);
        };
        initializeLanguage();
        initializeDisks();
        initializeEncrypt();
        initializeScenario();
    }, []);

    useEffect(() => {
        if (typeof storageScenario !== "undefined") {
            setStorageScenarioId(storageScenario);
            console.log("Global storageScenario id set to", storageScenario);
        }
    }, [storageScenario, setStorageScenarioId]);

    // handle case of disks not (yet) loaded
    if (!selectedDisks || !systemLanguage || !storageScenario) {
        return null;
    }

    return (
        <AnacondaPage title={_("Review and install")}>
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Language")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-language"}>
                        {systemLanguage}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </ReviewDescriptionList>
            <Title headingLevel="h3">
                {_("Installation destination")}
            </Title>
            <Alert
              isInline
              variant="warning"
              title={_("To prevent loss, make sure to backup your data. ")}
            >
                <p>
                    {getScenario(storageScenario).screenWarning}
                </p>
            </Alert>
            <ExpandableSection
              toggleText={_("Storage devices")}
              onToggle={() => setDisksExpanded(!disksExpanded)}
              isExpanded={disksExpanded}
              isIndented
            >
                <DataList isCompact>
                    {selectedDisks.map(selectedDisk => (
                        <DataListItem key={selectedDisk}>
                            <DataListItemRow>
                                <DataListItemCells
                                  dataListCells={[
                                      <DataListCell key={selectedDisk} id={idPrefix + "-disk-label-" + selectedDisk}>
                                          {_("Local standard disk")}
                                      </DataListCell>,
                                      <DataListCell key={"description-" + selectedDisk} id={idPrefix + "-disk-description-" + selectedDisk}>
                                          {deviceData && deviceData[selectedDisk] && deviceData[selectedDisk].description.v + " (" + selectedDisk + ")"}
                                      </DataListCell>,
                                      <DataListCell key={"size-" + selectedDisk} id={idPrefix + "-disk-size-" + selectedDisk}>
                                          {cockpit.format_bytes(deviceData && deviceData[selectedDisk] && deviceData[selectedDisk].size.v) + " " + _("total")}
                                      </DataListCell>
                                  ]}
                                />
                            </DataListItemRow>
                        </DataListItem>
                    ))}
                </DataList>
            </ExpandableSection>
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Storage Configuration")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-mode"}>
                        {getScenario(storageScenario).label}
                    </DescriptionListDescription>
                    <DescriptionListTerm>
                        {_("Disk Encryption")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-encrypt"}>
                        {encrypt ? _("Enabled") : _("Disabled")}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </ReviewDescriptionList>
        </AnacondaPage>
    );
};

export const ReviewConfigurationConfirmModal = ({ idPrefix, onNext, setNextWaitsConfirmation, storageScenarioId }) => {
    const scenario = getScenario(storageScenarioId);
    return (
        <Modal
          actions={[
              <Button
                id={idPrefix + "-disk-erase-confirm"}
                key="confirm"
                onClick={() => {
                    setNextWaitsConfirmation(false);
                    onNext();
                }}
                variant={scenario.buttonVariant}
              >
                  {scenario.buttonLabel}
              </Button>,
              <Button
                key="cancel"
                onClick={() => setNextWaitsConfirmation(false)}
                variant="link">
                  {_("Back")}
              </Button>
          ]}
          isOpen
          onClose={() => setNextWaitsConfirmation(false)}
          title={scenario.dialogWarningTitle}
          titleIconVariant={scenario.dialogTitleIconVariant}
          variant={ModalVariant.small}
        >
            {scenario.dialogWarning}
        </Modal>
    );
};
