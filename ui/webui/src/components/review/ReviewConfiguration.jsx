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
    DescriptionList, DescriptionListGroup,
    DescriptionListTerm, DescriptionListDescription,
    List, ListItem,
    Modal, ModalVariant,
    Stack,
} from "@patternfly/react-core";

import {
    getAppliedPartitioning,
    getPartitioningRequest,
    getPartitioningMethod,
} from "../../apis/storage.js";
import { checkDeviceInSubTree } from "../../helpers/storage.js";

import { AnacondaPage } from "../AnacondaPage.jsx";

import { getScenario } from "../storage/InstallationScenario.jsx";

import "./ReviewConfiguration.scss";

const _ = cockpit.gettext;

const ReviewDescriptionList = ({ children }) => {
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

const DeviceRow = ({ deviceData, disk, requests }) => {
    const data = deviceData[disk];
    const name = data.name.v;

    const renderRow = row => {
        const name = row["device-spec"];
        const action = (
            row.reformat
                ? (row["format-type"] ? cockpit.format(_("format as $0"), row["format-type"]) : null)
                : ((row["format-type"] === "biosboot") ? row["format-type"] : _("mount"))
        );
        const mount = row["mount-point"] || null;
        const actions = [action, mount].filter(Boolean).join(", ");
        const size = cockpit.format_bytes(deviceData[name].size.v);

        return (
            <ListItem className="pf-v5-u-font-size-s" key={name}>
                {name}, {size}: {actions}
            </ListItem>
        );
    };

    const partitionRows = requests?.filter(req => {
        if (!req.reformat && req["mount-point"] === "") {
            return false;
        }

        return checkDeviceInSubTree({ device: req["device-spec"], rootDevice: name, deviceData });
    }).map(renderRow) || [];

    return (
        <Stack id={`disk-${name}`} hasGutter>
            <span>{cockpit.format_bytes(data.size.v)} {name} {"(" + data.description.v + ")"}</span>
            <List>
                {partitionRows}
            </List>
        </Stack>
    );
};

export const ReviewConfiguration = ({ deviceData, diskSelection, language, localizationData, osRelease, requests, idPrefix, setIsFormValid, storageScenarioId }) => {
    const [encrypt, setEncrypt] = useState();

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
        setIsFormValid(true);
    }, [setIsFormValid]);

    return (
        <AnacondaPage title={_("Review and install")}>
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Operating system")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-operating-system"}>
                        {osRelease.PRETTY_NAME}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </ReviewDescriptionList>
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Language")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-language"}>
                        {language ? language["native-name"].v : localizationData.language}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </ReviewDescriptionList>
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Installation type")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-mode"}>
                        {getScenario(storageScenarioId).label}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </ReviewDescriptionList>
            {storageScenarioId !== "mount-point-mapping" &&
                <ReviewDescriptionList>
                    <DescriptionListGroup>
                        <DescriptionListTerm>
                            {_("Disk encryption")}
                        </DescriptionListTerm>
                        <DescriptionListDescription id={idPrefix + "-target-system-encrypt"}>
                            {encrypt ? _("Enabled") : _("Disabled")}
                        </DescriptionListDescription>
                    </DescriptionListGroup>
                </ReviewDescriptionList>}
            <ReviewDescriptionList>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Storage")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-storage"}>
                        <Stack hasGutter>
                            {diskSelection.selectedDisks.map(disk => {
                                return <DeviceRow key={disk} deviceData={deviceData} disk={disk} requests={storageScenarioId === "mount-point-mapping" ? requests : null} />;
                            })}
                        </Stack>
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
