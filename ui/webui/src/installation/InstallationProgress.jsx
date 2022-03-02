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
    EmptyState, EmptyStateBody, EmptyStateSecondaryActions,
    Progress
} from "@patternfly/react-core";

import { AddressContext } from "../Common.jsx";

import "./InstallationProgress.scss";

const _ = cockpit.gettext;

export class InstallationProgress extends React.Component {
    constructor (props) {
        super(props);
        this.state = {};
    }

    componentDidMount () {
        const client = cockpit.dbus("org.fedoraproject.Anaconda.Boss", { superuser: "try", bus: "none", address: this.context });
        client.call(
            "/org/fedoraproject/Anaconda/Boss",
            "org.fedoraproject.Anaconda.Boss",
            "InstallWithTasks", [],
        )
                .then(tasks => {
                    const taskProxy = client.proxy(
                        "org.fedoraproject.Anaconda.Task",
                        tasks[0]
                    );
                    const addEventListeners = () => {
                        taskProxy.addEventListener("ProgressChanged", (_, step, message) => {
                            this.setState({ message, step });
                        });
                        taskProxy.addEventListener("Failed", () => {
                            this.setState({ status: "danger" });
                        });
                        taskProxy.addEventListener("Started", () => {
                            this.setState({ progress: 50 });
                        });
                        taskProxy.addEventListener("Stopped", () => {
                            this.setState({ progress: 100 });
                            taskProxy.Finish().catch(
                                ex => {
                                    this.props.onAddNotification({ title: ex.name, message: ex.message, variant: "danger" });
                                    console.error(ex.message);
                                });
                        });
                        taskProxy.addEventListener("Succeeded", () => {
                            this.setState({ status: "success" });
                        });
                    };
                    taskProxy.wait(() => {
                        addEventListeners();
                        taskProxy.Start().then(() => {
                            this.setState({ steps: taskProxy.Steps });
                        }, console.error);
                    });
                }, console.error);
    }

    render () {
        const { steps, step, status, progress, message } = this.state;
        const label = cockpit.format("Step $0: $1", step, message);

        if (steps === undefined) { return null }

        return (
            <Bullseye>
                <EmptyState variant="large">
                    <EmptyStateBody>
                        <Progress
                          id="installation-progress"
                          label={label}
                          title={_("Running installation")}
                          value={progress}
                          valueText={label}
                          variant={status}
                        />
                    </EmptyStateBody>
                    {status === "success" &&
                    <EmptyStateSecondaryActions>
                        <Button>{_("Reboot")}</Button>
                    </EmptyStateSecondaryActions>}
                </EmptyState>
            </Bullseye>
        );
    }
}
InstallationProgress.contextType = AddressContext;
