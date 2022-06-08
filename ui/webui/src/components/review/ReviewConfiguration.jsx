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
    Modal, ModalVariant,
} from "@patternfly/react-core";

import {
    getSelectedDisks, getDeviceData,
} from "../../apis/storage.js";

import {
    getLanguage, getLanguageData,
} from "../../apis/localization.js";
import { AnacondaPage } from "../AnacondaPage.jsx";

const _ = cockpit.gettext;

export const ReviewConfiguration = ({ idPrefix }) => {
    const [deviceData, setDeviceData] = useState({});
    const [selectedDisks, setSelectedDisks] = useState();
    const [systemLanguage, setSystemLanguage] = useState();

    useEffect(() => {
        getLanguage()
                .then(res => {
                    getLanguageData({ lang: res }).then(res => {
                        setSystemLanguage(res["native-name"].v);
                    }, console.error);
                }, console.error);
        getSelectedDisks()
                .then(res => {
                    setSelectedDisks(res);
                    // get detailed data for the selected disks
                    res.forEach(disk => {
                        getDeviceData({ disk })
                                .then(res => {
                                    setDeviceData(d => ({ ...d, [disk]: res[0] }));
                                }, console.error);
                    });
                }, console.error);
    }, []);

    // handle case of disks not (yet) loaded
    if (!selectedDisks || !systemLanguage) {
        return null;
    }

    return (
        <AnacondaPage title={_("Review and install")}>
            <DescriptionList isHorizontal>
                <DescriptionListGroup>
                    <DescriptionListTerm>
                        {_("Language")}
                    </DescriptionListTerm>
                    <DescriptionListDescription id={idPrefix + "-target-system-language"}>
                        {systemLanguage}
                    </DescriptionListDescription>
                </DescriptionListGroup>
            </DescriptionList>
            <Title headingLevel="h3">
                {_("Installation destination")}
            </Title>
            <DataList>
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
        </AnacondaPage>
    );
};

export const ReviewConfigurationConfirmModal = ({ idPrefix, onNext, setNextWaitsConfirmation }) => {
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
                variant="danger"
              >
                  {_("Erase disks and install")}
              </Button>,
              <Button
                key="cancel"
                onClick={() => setNextWaitsConfirmation(false)}
                variant="secondary">
                  {_("Back")}
              </Button>
          ]}
          isOpen
          onClose={() => setNextWaitsConfirmation(false)}
          title={_("Erase disks and install?")}
          titleIconVariant="warning"
          variant={ModalVariant.small}
        >
            {_("The selected disks will be erased, this cannot be undone. Are you sure you want to continue with the installation?")}
        </Modal>
    );
};
