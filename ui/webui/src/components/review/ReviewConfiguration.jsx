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
    getAppliedPartitioning,
    getPartitioningRequest,
    getPartitioningMethod,
} from "../../apis/storage.js";

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

const checkDeviceInSubTree = (device, rootDevice, deviceData) => {
    const parents = device.parents.v;

    if (parents.length && parents[0] === rootDevice) {
        return true;
    } else if (parents.length && parents[0] !== rootDevice) {
        return checkDeviceInSubTree(deviceData[parents[0]], rootDevice, deviceData);
    } else {
        return false;
    }
};

const DeviceRow = ({ deviceData, disk, requests }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const data = deviceData[disk];
    const name = data.name.v;

    const renderRow = row => {
        const iconColumn = row.reformat.v ? <CheckCircleIcon /> : null;
        return {
            props: { key: row["device-spec"] },
            columns: [
                { title: row["device-spec"] },
                { title: row["format-type"] },
                { title: row["mount-point"] },
                { title: iconColumn },
            ]
        };
    };

    const partitionRows = requests?.filter(req => {
        const partitionName = Object.keys(deviceData).find(device => deviceData[device].name.v === req["device-spec"]);
        const device = deviceData[partitionName];

        return checkDeviceInSubTree(device, name, deviceData);
    }).map(renderRow) || [];

    return (
        <DataListItem id={`data-list-${name}`} isExpanded={isExpanded} key={name}>
            <DataListItemRow>
                <DataListToggle
                  buttonProps={{ isDisabled: requests === null }}
                  onClick={() => requests !== null ? setIsExpanded(!isExpanded) : {}}
                  isExpanded={isExpanded}
                  id={name + "-expander"}
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
                  columns={[_("Partition"), _("Format type"), _("Mount point"), _("Reformat")]}
                  rows={partitionRows} />
            </DataListContent>
        </DataListItem>
    );
};

export const ReviewConfiguration = ({ deviceData, diskSelection, language, requests, idPrefix, storageScenarioId }) => {
    const [encrypt, setEncrypt] = useState();
    const [showLanguageSection, setShowLanguageSection] = useState(true);
    const [showInstallationDestSection, setShowInstallationDestSection] = useState(true);

    useEffect(() => {
        const initializeEncrypt = async () => {
            const partitioning = await getAppliedPartitioning().catch(console.error);
            const method = await getPartitioningMethod({ partitioning }).catch(console.error);
            if (method === "AUTOMATIC") {
                const request = await getPartitioningRequest({ partitioning }).catch(console.error);
                setEncrypt(request.encrypted.v);
            }
        };
        initializeEncrypt();
    }, []);

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
              id={`${idPrefix}-language`}
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
                            {language["native-name"].v}
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
                        {storageScenarioId !== "mount-point-mapping" &&
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
                    {diskSelection.selectedDisks.map(disk => {
                        return <DeviceRow key={disk} deviceData={deviceData} disk={disk} requests={storageScenarioId === "mount-point-mapping" ? requests : null} />;
                    })}
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
