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
    Button,
    Flex,
    FlexItem,
    ProgressStep,
    ProgressStepper,
    Stack,
    TextContent,
    Text,
} from "@patternfly/react-core";
import {
    InProgressIcon,
    PendingIcon,
    CheckCircleIcon,
    ExclamationCircleIcon
} from "@patternfly/react-icons";
import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { AddressContext } from "../Common.jsx";
import { BossClient, getSteps, installWithTasks } from "../../apis/boss.js";
import { exitGui } from "../../helpers/exit.js";
import "./InstallationProgress.scss";

const _ = cockpit.gettext;

export class InstallationProgress extends React.Component {
    constructor (props) {
        super(props);
        this.state = { statusMessage: "", currentProgressStep: 0 };
        this.logViewerRef = React.createRef();
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
                            // FIXME: hardcoded progress steps
                            //        - if ProgressStepper turns out to be viable,
                            //          use a proper DBus API for progress tep discovery
                            //          and switching
                            //
                            // storage
                            } else if (step <= 3) {
                                this.setState({ currentProgressStep: 0 });
                            // payload
                            } else if (step === 4) {
                                this.setState({ currentProgressStep: 1 });
                            // configuration
                            } else if (step >= 5 && step <= 11) {
                                this.setState({ currentProgressStep: 2 });
                            // bootloader
                            } else if (step >= 12) {
                                this.setState({ currentProgressStep: 3 });
                            }
                            if (message) {
                                this.setState({ statusMessage: message });
                            } else {
                                this.setState({ step });
                            }
                        });
                        taskProxy.addEventListener("Failed", () => {
                            this.setState({ status: "danger" });
                        });
                        taskProxy.addEventListener("Stopped", () => {
                            taskProxy.Finish().catch(this.props.onAddErrorNotification);
                        });
                        taskProxy.addEventListener("Succeeded", () => {
                            this.setState({ status: "success", currentProgressStep: 4 });
                        });
                    };
                    taskProxy.wait(() => {
                        addEventListeners();
                        taskProxy.Start().catch(console.error);
                    });
                }, console.error);
    }

    render () {
        const idPrefix = this.props.idPrefix;
        const { steps, currentProgressStep, status, statusMessage } = this.state;

        const progressSteps = [
            {
                title: _("Storage configuration"),
                id: "installation-progress-step-storage",
                description: _("Storage configuration: Storage is currently being configured."),
            },
            {
                title: _("Software installation"),
                id: "installation-progress-step-payload",
                description: _("Software installation: Storage configuration complete. The software is now being installed onto your device."),
            },
            {
                title: _("System configuration"),
                id: "installation-progress-step-configuration",
                description: _("System configuration: Software installation complete. The system is now being configured."),
            },
            {
                title: _("Finalization"),
                id: "installation-progress-step-boot-loader",
                description: _("Finalizing: The system configuration is complete. Finalizing installation may take a few moments."),
            },
        ];

        if (steps === undefined) {
            return null;
        }

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
            <Stack hasGutter className={idPrefix + "-status-" + status}>
                <EmptyStatePanel
                  icon={icon}
                  loading={!icon}
                  paragraph={
                      <Flex direction={{ default: "column" }}>
                          <TextContent>
                              {currentProgressStep < 4 ? progressSteps[currentProgressStep].description : null}
                          </TextContent>
                          <FlexItem spacer={{ default: "spacerXl" }} />
                          <ProgressStepper isCenterAligned>
                              {progressSteps.map((progressStep, index) => {
                                  let variant = "pending";
                                  let ariaLabel = _("pending step");
                                  let phaseText = _("Pending");
                                  let statusText = "";
                                  let phaseIcon = <PendingIcon />;
                                  if (index < currentProgressStep) {
                                      variant = "success";
                                      ariaLabel = _("completed step");
                                      phaseText = _("Completed");
                                      phaseIcon = <CheckCircleIcon />;
                                  } else if (index === currentProgressStep) {
                                      variant = status === "danger" ? status : "info";
                                      ariaLabel = _("current step");
                                      phaseText = _("In progress");
                                      statusText = statusMessage;
                                      if (status === "danger") {
                                          phaseIcon = <ExclamationCircleIcon />;
                                      } else {
                                          phaseIcon = <InProgressIcon />;
                                      }
                                  }
                                  return (
                                      <ProgressStep
                                        aria-label={ariaLabel}
                                        id={idPrefix + "-step-" + index}
                                        isCurrent={index === currentProgressStep}
                                        icon={phaseIcon}
                                        titleId={progressStep.id}
                                        key={index}
                                        variant={variant}
                                        description={
                                            <Flex direction={{ default: "column" }}>
                                                <FlexItem spacer={{ default: "spacerNone" }}>
                                                    <Text>{phaseText}</Text>
                                                </FlexItem>
                                                <FlexItem spacer={{ default: "spacerNone" }}>
                                                    <Text>{statusText}</Text>
                                                </FlexItem>
                                            </Flex>
                                        }
                                      >
                                          {progressStep.title}
                                      </ProgressStep>
                                  );
                              })}
                          </ProgressStepper>
                      </Flex>
                  }
                  secondary={
                      status === "success" &&
                      <Button onClick={exitGui}>{_("Reboot")}</Button>
                  }
                  title={title}
                  headingLevel="h2"
                />
            </Stack>
        );
    }
}
InstallationProgress.contextType = AddressContext;
