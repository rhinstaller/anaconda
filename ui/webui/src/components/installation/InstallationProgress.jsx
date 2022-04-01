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
import React from "react";

import {
    Bullseye, Button,
    Progress,
    Text,
} from "@patternfly/react-core";
import { CheckCircleIcon, ExclamationCircleIcon } from "@patternfly/react-icons";
import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";

import { AddressContext } from "../Common.jsx";

import { BossClient, getSteps, installWithTasks } from "../../apis/boss.js";

import { exitGui } from "../../helpers/exit.js";

import "./InstallationProgress.scss";

const _ = cockpit.gettext;

export class InstallationProgress extends React.Component {
    constructor (props) {
        super(props);
        this.state = {};
    }

    componentDidMount () {
        installWithTasks()
                .then(tasks => {
                    const taskProxy = new BossClient().client.proxy(
                        "org.fedoraproject.Anaconda.Task",
                        tasks[0]
                    );

                    const addEventListeners = () => {
                        taskProxy.addEventListener("ProgressChanged", (_, step, message) => {
                            if (step === 0) {
                                getSteps({ task: tasks[0] })
                                        .then(
                                            ret => this.setState({ steps: ret.v }),
                                            this.props.onAddErrorNotification
                                        );
                            }
                            this.setState({ message, step });
                        });
                        taskProxy.addEventListener("Failed", () => {
                            this.setState({ status: "danger" });
                        });
                        taskProxy.addEventListener("Stopped", () => {
                            taskProxy.Finish().catch(this.props.onAddErrorNotification);
                        });
                        taskProxy.addEventListener("Succeeded", () => {
                            this.setState({ status: "success" });
                        });
                    };
                    taskProxy.wait(() => {
                        addEventListeners();
                        taskProxy.Start().catch(console.error);
                    });
                }, console.error);
    }

    render () {
        const { steps, step, status, message } = this.state;

        if (steps === undefined) { return null }

        let icon;
        let title;
        if (status === "success") {
            icon = CheckCircleIcon;
            title = _("Installed");
        } else if (status === "danger") {
            icon = ExclamationCircleIcon;
            title = _("Installation failed");
        } else {
            title = _("Installing");
        }

        return (
            <Bullseye className={"installation-progress-status-" + status}>
                <EmptyStatePanel
                  icon={icon}
                  loading={!icon}
                  paragraph={
                      status !== "success"
                          ? <Progress
                              id="installation-progress"
                              label={cockpit.format("$0 of $1", step, steps)}
                              max={steps}
                              min={0}
                              title={message}
                              value={step}
                              valueText={cockpit.format("$0 of $1", step, steps)}
                              variant={status}
                          />
                          : <Text>{_("Fedora is successfully installed. To begin using it, reboot your system.")}</Text>
                  }
                  secondary={
                      status === "success" &&
                      <Button onClick={exitGui}>{_("Reboot")}</Button>
                  }
                  title={title}
                />
            </Bullseye>
        );
    }
}
InstallationProgress.contextType = AddressContext;
