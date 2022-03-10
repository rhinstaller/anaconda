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
    Page, Wizard
} from "@patternfly/react-core";

import { AddressContext } from "./Common.jsx";
import { InstallationDestination } from "./storage/InstallationDestination.jsx";
import { InstallationLanguage } from "./installation/InstallationLanguage.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration } from "./installation/ReviewConfiguration.jsx";

import { readConf } from "../helpers/conf.js";

import { usePageLocation } from "hooks";

const _ = cockpit.gettext;

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

    const onAddErrorNotification = ex => {
        onAddNotification({ title: ex.name, message: ex.message, variant: "danger" });
    };

    // Postpone rendering anything until we read the dbus address and the default configuration
    if (!address || !conf) {
        return null;
    }

    console.info("conf: ", conf);
    const wrapWithContext = children => {
        return (
            <AddressContext.Provider value={address}>
                {children}
            </AddressContext.Provider>
        );
    };

    const steps = [
        {
            id: "installation-language",
            name: _("Installation language"),
            component: wrapWithContext(<InstallationLanguage />),
            stepNavItemProps: { id: "installation-language" }
        },
        {
            id: "installation-destination",
            name: _("Storage configuration"),
            component: wrapWithContext(<InstallationDestination onAddErrorNotification={onAddErrorNotification} />),
            stepNavItemProps: { id: "installation-destination" }
        },
        {
            id: "review-configuration",
            name: _("Review"),
            component: wrapWithContext(<ReviewConfiguration />),
            nextButtonText: _("Begin installation"),
            stepNavItemProps: { id: "review-configuration" }
        },
        {
            id: "installation-progress",
            name: _("Installation progress"),
            component: wrapWithContext(<InstallationProgress onAddErrorNotification={onAddErrorNotification} />),
            stepNavItemProps: { id: "installation-progress" },
            isFinishedStep: true
        },
    ];
    const startAtStep = steps.findIndex(step => step.id === path[0]) + 1;
    const goToStep = newStep => cockpit.location.go([newStep.id]);
    const title = _("Anaconda Installer");

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
            <Wizard
              cancelButtonText={_("Quit")}
              description={_("PRE-RELEASE/TESTING")}
              descriptionId="wizard-top-level-description"
              hideClose
              mainAriaLabel={`${title} content`}
              navAriaLabel={`${title} steps`}
              onBack={goToStep}
              onGoToStep={goToStep}
              onNext={goToStep}
              startAtStep={startAtStep}
              steps={steps}
              title={_("Fedora Rawhide installation")}
              titleId="wizard-top-level-title"
            />
        </Page>
    );
};
