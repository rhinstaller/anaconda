/*
 * Copyright (C) 2021 Red Hat, Inc.
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
    AlertGroup, AlertVariant, AlertActionCloseButton, Alert,
    Page,
} from "@patternfly/react-core";

import { AddressContext } from "./Common.jsx";
import { AnacondaHeader } from "./AnacondaHeader.jsx";
import { AnacondaWizard } from "./AnacondaWizard.jsx";

import { BossClient } from "../apis/boss.js";
import { LocalizationClient } from "../apis/localization.js";
import { StorageClient } from "../apis/storage.js";

import { readBuildstamp, getIsFinal } from "../helpers/betanag.js";
import { readConf } from "../helpers/conf.js";

const _ = cockpit.gettext;

export const Application = () => {
    const [address, setAddress] = useState();
    const [beta, setBeta] = useState();
    const [conf, setConf] = useState();
    const [notifications, setNotifications] = useState({});

    useEffect(() => {
        cockpit.file("/run/anaconda/bus.address").watch(address => {
            const clients = [
                new LocalizationClient(address),
                new StorageClient(address),
                new BossClient(address)
            ];
            clients.forEach(c => c.init());

            setAddress(address);
        });

        readConf().then(
            setConf,
            ex => console.error("Failed to parse anaconda configuration")
        );

        readBuildstamp().then(
            buildstamp => setBeta(!getIsFinal(buildstamp)),
            ex => console.error("Failed to parse anaconda buildstamp file")
        );
    }, []);

    const onAddNotification = (notificationProps) => {
        setNotifications({
            ...notifications,
            [notifications.length]: { index: notifications.length, ...notificationProps }
        });
    };

    const onAddErrorNotification = ex => {
        onAddNotification({ title: ex.name, message: ex.message, variant: "danger" });
    };

    // Postpone rendering anything until we read the dbus address and the default configuration
    if (!address || !conf) {
        return null;
    }
    console.info("conf: ", conf);

    const title = _("Anaconda Installer");

    return (
        <Page
          data-debug={conf.Anaconda.debug}
          additionalGroupedContent={
              <AnacondaHeader beta={beta} title={title} />
          }
          groupProps={{
              sticky: "top"
          }}
        >
            {Object.keys(notifications).length > 0 &&
            <AlertGroup isToast isLiveRegion>
                {Object.keys(notifications).map(idx => {
                    const notification = notifications[idx];
                    const newNotifications = { ...notifications };
                    delete newNotifications[notification.index];

                    return (
                        <Alert
                          variant={AlertVariant[notification.variant]}
                          title={notification.title}
                          actionClose={
                              <AlertActionCloseButton
                                title={notifications.title}
                                onClose={() => setNotifications(newNotifications)}
                              />
                          }
                          key={notification.index}>
                            {notification.message}
                        </Alert>
                    );
                })}
            </AlertGroup>}
            <AddressContext.Provider value={address}>
                <AnacondaWizard onAddErrorNotification={onAddErrorNotification} title={title} />
            </AddressContext.Provider>
        </Page>
    );
};
