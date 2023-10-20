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

import React, { useCallback, useEffect, useState } from "react";

import {
    Page, PageGroup,
} from "@patternfly/react-core";

import { read_os_release as readOsRelease } from "os-release.js";

import { WithDialogs } from "dialogs.jsx";
import { AddressContext, LanguageContext, SystemTypeContext, OsReleaseContext } from "./Common.jsx";
import { AnacondaHeader } from "./AnacondaHeader.jsx";
import { AnacondaWizard } from "./AnacondaWizard.jsx";
import { CriticalError, errorHandlerWithContext, bugzillaPrefiledReportURL } from "./Error.jsx";

import { BossClient } from "../apis/boss.js";
import { LocalizationClient, initDataLocalization, startEventMonitorLocalization } from "../apis/localization.js";
import { StorageClient, initDataStorage, startEventMonitorStorage } from "../apis/storage.js";
import { PayloadsClient } from "../apis/payloads";
import { RuntimeClient, initDataRuntime, startEventMonitorRuntime } from "../apis/runtime";
import { NetworkClient, initDataNetwork, startEventMonitorNetwork } from "../apis/network.js";

import { setCriticalErrorAction } from "../actions/miscellaneous-actions.js";

import { readConf } from "../helpers/conf.js";
import { debug } from "../helpers/log.js";
import { useReducerWithThunk, reducer, initialState } from "../reducer.js";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

export const Application = () => {
    const [address, setAddress] = useState();
    const [conf, setConf] = useState();
    const [language, setLanguage] = useState();
    const [osRelease, setOsRelease] = useState("");
    const [state, dispatch] = useReducerWithThunk(reducer, initialState);
    const [storeInitilized, setStoreInitialized] = useState(false);
    const criticalError = state?.error?.criticalError;
    const [jsError, setJsEroor] = useState();

    const onCritFail = useCallback((contextData) => {
        return errorHandlerWithContext(contextData, exc => dispatch(setCriticalErrorAction(exc)));
    }, [dispatch]);

    useEffect(() => {
        // Before unload ask the user for verification
        window.onbeforeunload = e => "";

        // Listen on JS errors
        window.onerror = (message, url, line, col, errObj) => {
            setJsEroor(errObj);
        };

        cockpit.file("/run/anaconda/bus.address").watch(address => {
            setCriticalErrorAction();
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
                initDataRuntime({ dispatch }),
            ])
                    .then(() => {
                        setStoreInitialized(true);
                        startEventMonitorStorage({ dispatch });
                        startEventMonitorLocalization({ dispatch });
                        startEventMonitorNetwork({ dispatch });
                        startEventMonitorRuntime({ dispatch });
                    }, onCritFail({ context: N_("Reading information about the computer failed.") }));
        });

        readConf().then(
            setConf,
            onCritFail({ context: N_("Reading installer configuration failed.") })
        );

        readOsRelease().then(osRelease => setOsRelease(osRelease));
    }, [dispatch, onCritFail]);

    // Postpone rendering anything until we read the dbus address and the default configuration
    if (!criticalError && (!address || !conf || !osRelease || !storeInitilized)) {
        debug("Loading initial data...");
        return null;
    }

    // On live media rebooting the system will actually shut it off
    const systemType = conf?.["Installation System"].type;
    const title = cockpit.format(_("$0 installation"), osRelease.PRETTY_NAME);

    const bzReportURL = bugzillaPrefiledReportURL({
        product: osRelease.REDHAT_BUGZILLA_PRODUCT,
        version: osRelease.REDHAT_BUGZILLA_PRODUCT_VERSION,
    });

    const page = (
        <OsReleaseContext.Provider value={osRelease}>
            <SystemTypeContext.Provider value={systemType}>
                <Page
                  data-debug={conf.Anaconda.debug}
                >
                    {(criticalError || jsError) &&
                    <CriticalError
                      exception={{ ...criticalError, jsMessage: jsError?.message, backendMessage: criticalError?.message, stack: jsError?.stack }}
                      isConnected={state.network.connected}
                      reportLinkURL={bzReportURL} />}
                    {!jsError &&
                    <>
                        <PageGroup stickyOnBreakpoint={{ default: "top" }}>
                            <AnacondaHeader
                              title={title}
                              reportLinkURL={bzReportURL}
                              isConnected={state.network.connected}
                              onCritFail={onCritFail}
                            />
                        </PageGroup>
                        <AddressContext.Provider value={address}>
                            <WithDialogs>
                                <AnacondaWizard
                                  onCritFail={onCritFail}
                                  title={title}
                                  storageData={state.storage}
                                  localizationData={state.localization}
                                  dispatch={dispatch}
                                  conf={conf}
                                  osRelease={osRelease}
                                />
                            </WithDialogs>
                        </AddressContext.Provider>
                    </>}
                </Page>
            </SystemTypeContext.Provider>
        </OsReleaseContext.Provider>
    );

    return (
        <WithDialogs>
            <LanguageContext.Provider value={{ language, setLanguage }}>
                {page}
            </LanguageContext.Provider>
        </WithDialogs>
    );
};
