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

import { read_os_release as readOsRelease } from "os-release.js";

import { WithDialogs } from "dialogs.jsx";
import { AddressContext, LanguageContext } from "./Common.jsx";
import { AnacondaHeader } from "./AnacondaHeader.jsx";
import { AnacondaWizard } from "./AnacondaWizard.jsx";
import { CriticalError } from "./Error.jsx";

import { BossClient } from "../apis/boss.js";
import { LocalizationClient, initDataLocalization, startEventMonitorLocalization } from "../apis/localization.js";
import { StorageClient, initDataStorage, startEventMonitorStorage } from "../apis/storage.js";
import { PayloadsClient } from "../apis/payloads";
import { RuntimeClient, getIsFinal } from "../apis/runtime";

import { readConf } from "../helpers/conf.js";
import { debug } from "../helpers/log.js";
import { useReducerWithThunk, reducer, initialState } from "../reducer.js";

export const Application = () => {
    const [address, setAddress] = useState();
    const [criticalError, setCriticalError] = useState();
    const [beta, setBeta] = useState();
    const [conf, setConf] = useState();
    const [language, setLanguage] = useState();
    const [notifications, setNotifications] = useState({});
    const [osRelease, setOsRelease] = useState("");
    const [state, dispatch] = useReducerWithThunk(reducer, initialState);
    const [storeInitilized, setStoreInitialized] = useState(false);

    useEffect(() => {
        cockpit.file("/run/anaconda/bus.address").watch(address => {
            setCriticalError();
            const clients = [
                new LocalizationClient(address),
                new StorageClient(address),
                new PayloadsClient(address),
                new RuntimeClient(address),
                new BossClient(address)
            ];
            clients.forEach(c => c.init());

            setAddress(address);

            Promise.all([
                initDataStorage({ dispatch }),
                initDataLocalization({ dispatch }),
            ])
                    .then(() => {
                        setStoreInitialized(true);

                        startEventMonitorStorage({ dispatch });
                        startEventMonitorLocalization({ dispatch });
                    }, setCriticalError);

            getIsFinal().then(
                isFinal => setBeta(!isFinal),
                setCriticalError
            );
        });

        readConf().then(
            setConf,
            setCriticalError
        );

        readOsRelease().then(osRelease => setOsRelease(osRelease));
    }, [dispatch]);

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
    if (!criticalError && (!address || !conf || beta === undefined || !osRelease || !storeInitilized)) {
        debug("Loading initial data...");
        return null;
    }

    // On live media rebooting the system will actually shut it off
    const isBootIso = conf?.["Installation System"].type === "BOOT_ISO";
    const title = cockpit.format("$0 installation", osRelease.PRETTY_NAME);

    const page = (
        criticalError
            ? <CriticalError exception={criticalError} isBootIso={isBootIso} />
            : (
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
                        <WithDialogs>
                            <AnacondaWizard
                              isBootIso={isBootIso}
                              onAddErrorNotification={onAddErrorNotification}
                              title={title}
                              storageData={state.storage}
                              localizationData={state.localization}
                              dispatch={dispatch}
                              conf={conf}
                              osRelease={osRelease}
                            />
                        </WithDialogs>
                    </AddressContext.Provider>
                </Page>
            )
    );

    return (
        <WithDialogs>
            <LanguageContext.Provider value={{ language, setLanguage }}>
                {page}
            </LanguageContext.Provider>
        </WithDialogs>
    );
};
