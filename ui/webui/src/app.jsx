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

import { InstallationLanguage } from "./InstallationLanguage.jsx";
import { Summary } from "./Summary.jsx";
import { AddressContext, ConfContext } from "./Common.jsx";
import { readConf } from "./helpers/conf.js";

import { usePageLocation } from "hooks";

export const Application = () => {
    const [address, setAddress] = useState();
    const [notifications, setNotifications] = useState({});
    const [conf, setConf] = useState();
    const { path } = usePageLocation();

    useEffect(() => cockpit.file("/run/anaconda/bus.address").watch(setAddress), []);
    useEffect(() => readConf().then(setConf, ex => console.error("Failed to parse anaconda configuration")), []);

    const onAddNotification = (notificationProps) => {
        setNotifications({
            ...notifications,
            [notifications.length]: { index: notifications.length, ...notificationProps }
        });
    };

    // Postpone rendering anything until we read the dbus address and the default configuration
    if (!address || !conf) {
        return null;
    }

    console.info("conf: ", conf);
    return (
        <Page data-debug={conf.Anaconda.debug}>
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
                <ConfContext.Provider value={conf}>
                    {!path.length > 0 && <InstallationLanguage />}
                </ConfContext.Provider>
            </AddressContext.Provider>
            {path.length > 0 &&
            <AddressContext.Provider value={address}>
                <ConfContext.Provider value={conf}>
                    <Summary onAddNotification={onAddNotification} />
                </ConfContext.Provider>
            </AddressContext.Provider>}
        </Page>
    );
};
