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
    Page, PageGroup,
} from "@patternfly/react-core";

import { read_os_release as readOsRelease } from "os-release.js";

import { WithDialogs } from "dialogs.jsx";
import { AddressContext, LanguageContext } from "./Common.jsx";
import { AnacondaHeader } from "./AnacondaHeader.jsx";
import { AnacondaWizard } from "./AnacondaWizard.jsx";
import { CriticalError, errorHandlerWithContext, bugzillaPrefiledReportURL } from "./Error.jsx";

import { BossClient } from "../apis/boss.js";
import { LocalizationClient, initDataLocalization, startEventMonitorLocalization } from "../apis/localization.js";
import { StorageClient, initDataStorage, startEventMonitorStorage } from "../apis/storage.js";
import { PayloadsClient } from "../apis/payloads";
import { RuntimeClient, getIsFinal } from "../apis/runtime";
import { NetworkClient, initDataNetwork, startEventMonitorNetwork } from "../apis/network.js";

import { readConf } from "../helpers/conf.js";
import { debug } from "../helpers/log.js";
import { useReducerWithThunk, reducer, initialState } from "../reducer.js";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

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

    const onCritFail = (contextData) => {
        return errorHandlerWithContext(contextData, setCriticalError);
    };

    useEffect(() => {
        // Before unload ask the user for verification
        window.onbeforeunload = e => "";
        cockpit.file("/run/anaconda/bus.address").watch(address => {
            setCriticalError();
            const clients = [
                new LocalizationClient(address),
                new StorageClient(address),
                new PayloadsClient(address),
                new RuntimeClient(address),
                new BossClient(address),
                new NetworkClient(address),
            ];
            clients.forEach(c => c.init());

            setAddress(address);

            Promise.all([
                initDataStorage({ dispatch }),
                initDataLocalization({ dispatch }),
                initDataNetwork({ dispatch }),
            ])
                    .then(() => {
                        setStoreInitialized(true);
                        startEventMonitorStorage({ dispatch });
                        startEventMonitorLocalization({ dispatch });
                        startEventMonitorNetwork({ dispatch });
                    }, onCritFail({ context: N_("Reading information about the computer failed.") }));

            getIsFinal().then(
                isFinal => setBeta(!isFinal),
                onCritFail({ context: N_("Reading installer version information failed.") })
            );
        });

        readConf().then(
            setConf,
            onCritFail({ context: N_("Reading installer configuration failed.") })
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
    const title = cockpit.format(_("$0 installation"), osRelease.PRETTY_NAME);

    const bzReportURL = bugzillaPrefiledReportURL({
        product: osRelease.REDHAT_BUGZILLA_PRODUCT,
        version: osRelease.REDHAT_BUGZILLA_PRODUCT_VERSION,
    });

    const page = (
        <>
            {criticalError &&
            <CriticalError exception={criticalError} isBootIso={isBootIso} reportLinkURL={bzReportURL} />}
            <Page
              data-debug={conf.Anaconda.debug}
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
                <PageGroup stickyOnBreakpoint={{ default: "top" }}>
                    <AnacondaHeader beta={beta} title={title} reportLinkURL={bzReportURL} />
                </PageGroup>
                <AddressContext.Provider value={address}>
                    <WithDialogs>
                        <AnacondaWizard
                          isBootIso={isBootIso}
                          onCritFail={onCritFail}
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
        </>
    );

    return (
        <WithDialogs>
            <LanguageContext.Provider value={{ language, setLanguage }}>
                {page}
            </LanguageContext.Provider>
        </WithDialogs>
    );
};
