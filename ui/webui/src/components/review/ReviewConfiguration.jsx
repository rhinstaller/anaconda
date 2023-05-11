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
    Badge,
    Button,
    Flex,
    Title,
    DataList, DataListItem,
    DataListToggle,
    DataListItemRow, DataListItemCells,
    DataListCell,
    DataListContent,
    DescriptionList, DescriptionListGroup,
    DescriptionListTerm, DescriptionListDescription,
    ExpandableSection,
    Modal, ModalVariant,
    Alert,
    Tooltip,
} from "@patternfly/react-core";

import {
    getSelectedDisks,
    getDeviceData,
    getAppliedPartitioning,
    getManualPartitioningRequests,
    getPartitioningRequest,
    getPartitioningMethod,
} from "../../apis/storage.js";

import {
    getLanguage, getLanguageData,
} from "../../apis/localization.js";
import { AnacondaPage } from "../AnacondaPage.jsx";

import { getScenario } from "../storage/StorageConfiguration.jsx";
import { CheckCircleIcon } from "@patternfly/react-icons";

import { ListingTable } from "cockpit-components-table.jsx";

import "./ReviewConfiguration.scss";

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

const DeviceRow = ({ name, data, requests }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const renderRow = row => {
        const iconColumn = row.reformat.v ? <CheckCircleIcon /> : null;
        return {
            props: { key: row["device-spec"].v },
            columns: [
                { title: row["device-spec"].v },
                { title: row["format-type"].v },
                { title: row["mount-point"].v },
                { title: iconColumn },
            ]
        };
    };

    const imageRows = requests?.filter(req => req["device-spec"].v.includes(name)).map(renderRow) || [];

    const columnTitles = [
        _("Partition"),
        _("Format type"),
        _("Mount"),
        _("Reformat"),
    ];

    return (
        <DataListItem id={`data-list-${name}`} isExpanded={isExpanded} key={name}>
            <DataListItemRow>
                <DataListToggle
                  onClick={() => requests !== null ? setIsExpanded(!isExpanded) : {}}
                  isExpanded={isExpanded}
                  id={name + "-expander"}
                  buttonProps={{ isDisabled: requests === null }}
                />
                <DataListItemCells
                  dataListCells={[
                      <DataListCell key={name + "-name"}>
                          <Flex>
                              <span id={`installation-review-disk-label-${name}`} className="review-disk-label">{name}</span>
                              <span id={`installation-review-disk-description-${name}`}>{"(" + data.description.v + ")"}</span>
                              <Tooltip content={_("Total disk size")}>
                                  <Badge screenReaderText={_("Total disk size")}>{cockpit.format_bytes(data.size.v)}</Badge>
                              </Tooltip>
                          </Flex>
                      </DataListCell>
                  ]}
                />
            </DataListItemRow>
            <DataListContent isHidden={!isExpanded}>
                <ListingTable
                  id="partitions-table"
                  aria-label={_("Disk partitions")}
                  emptyCaption={_("No partitions found")}
                  variant="compact"
                  columns={columnTitles}
                  rows={imageRows} />
            </DataListContent>
        </DataListItem>
    );
};

export const ReviewConfiguration = ({ idPrefix, storageScenarioId }) => {
    const [deviceData, setDeviceData] = useState({});
    const [selectedDisks, setSelectedDisks] = useState();
    const [systemLanguage, setSystemLanguage] = useState();
    const [encrypt, setEncrypt] = useState();
    const [requests, setRequests] = useState(null);
    const [showLanguageSection, setShowLanguageSection] = useState(true);
    const [showInstallationDestSection, setShowInstallationDestSection] = useState(true);

    useEffect(() => {
        const initializeLanguage = async () => {
            const lang = await getLanguage().catch(console.error);
            const langData = await getLanguageData({ lang }).catch(console.error);
            setSystemLanguage(langData["native-name"].v);
        };
        const initializeDisks = async () => {
            const selDisks = await getSelectedDisks().catch(console.error);
            setSelectedDisks(selDisks);
            for (const disk of selDisks) {
                const devData = await getDeviceData({ disk }).catch(console.error);
                setDeviceData(d => ({ ...d, [disk]: devData[0] }));
            }
        };
        const initializeEncrypt = async () => {
            const partitioning = await getAppliedPartitioning().catch(console.error);
            const method = await getPartitioningMethod({ partitioning }).catch(console.error);
            if (method === "AUTOMATIC") {
                const request = await getPartitioningRequest({ partitioning }).catch(console.error);
                setEncrypt(request.encrypted.v);
            } else {
                const requests = await getManualPartitioningRequests({ partitioning });
                setRequests(requests);
            }
        };
        initializeLanguage();
        initializeDisks();
        initializeEncrypt();
    }, []);

    // handle case of disks not (yet) loaded
    if (!selectedDisks || !systemLanguage) {
        return null;
    }

    return (
        <AnacondaPage title={_("Review and install")}>
            <Alert
              isInline
              variant="warning"
              title={_("To prevent loss, make sure to backup your data. ")}
            >
                <p>
                    {getScenario(storageScenarioId).screenWarning}
                </p>
            </Alert>
            <ExpandableSection
              className="review-expandable-section"
              toggleText={<Title headingLevel="h3">{_("Language")}</Title>}
              onToggle={() => setShowLanguageSection(!showLanguageSection)}
              isExpanded={showLanguageSection}
              isIndented
            >
                <ReviewDescriptionList>
                    <DescriptionListGroup>
                        <DescriptionListTerm className="description-list-term">
                            {_("Language")}
                        </DescriptionListTerm>
                        <DescriptionListDescription className="description-list-description" id={idPrefix + "-target-system-language"}>
                            {systemLanguage}
                        </DescriptionListDescription>
                    </DescriptionListGroup>
                </ReviewDescriptionList>
            </ExpandableSection>
            <ExpandableSection
              className="review-expandable-section"
              toggleText={<Title headingLevel="h3">{_("Installation destination")}</Title>}
              onToggle={() => setShowInstallationDestSection(!showInstallationDestSection)}
              isExpanded={showInstallationDestSection}
              isIndented
            >
                <ReviewDescriptionList>
                    <DescriptionListGroup>
                        <DescriptionListTerm className="description-list-term">
                            {_("Storage Configuration")}
                        </DescriptionListTerm>
                        <DescriptionListDescription className="description-list-description" id={idPrefix + "-target-system-mode"}>
                            {getScenario(storageScenarioId).label}
                        </DescriptionListDescription>
                        {storageScenarioId !== "custom-mount-point" &&
                        <>
                            <DescriptionListTerm className="description-list-term">
                                {_("Disk Encryption")}
                            </DescriptionListTerm>
                            <DescriptionListDescription className="description-list-description" id={idPrefix + "-target-system-encrypt"}>
                                {encrypt ? _("Enabled") : _("Disabled")}
                            </DescriptionListDescription>
                        </>}
                    </DescriptionListGroup>
                </ReviewDescriptionList>
                <Title className="storage-devices-configuration-title" headingLevel="h4">{_("Storage devices and configurations")}</Title>
                <DataList isCompact>
                    {Object.keys(deviceData).map(deviceName =>
                        <DeviceRow key={deviceName} name={deviceName} data={deviceData[deviceName]} requests={requests} />
                    )}
                </DataList>
            </ExpandableSection>
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
