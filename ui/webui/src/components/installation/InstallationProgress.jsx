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
import React, { useContext, useState, useEffect, useRef } from "react";
import {
    Button,
    Flex,
    FlexItem,
    ProgressStep,
    ProgressStepper,
    Stack,
    Text,
} from "@patternfly/react-core";
import {
    InProgressIcon,
    PendingIcon,
    CheckCircleIcon,
    ExclamationCircleIcon
} from "@patternfly/react-icons";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { SystemTypeContext, OsReleaseContext } from "../Common.jsx";

import { BossClient, getSteps, installWithTasks } from "../../apis/boss.js";
import { exitGui } from "../../helpers/exit.js";

import "./InstallationProgress.scss";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

export const InstallationProgress = ({ onCritFail, idPrefix }) => {
    const [status, setStatus] = useState();
    const [statusMessage, setStatusMessage] = useState("");
    const [steps, setSteps] = useState();
    const [currentProgressStep, setCurrentProgressStep] = useState(0);
    const refStatusMessage = useRef("");
    const isBootIso = useContext(SystemTypeContext) === "BOOT_ISO";
    const osRelease = useContext(OsReleaseContext);

    useEffect(() => {
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
                                            ret => setSteps(ret.v),
                                            onCritFail()
                                        );
                            // FIXME: hardcoded progress steps
                            //        - if ProgressStepper turns out to be viable,
                            //          use a proper DBus API for progress tep discovery
                            //          and switching
                            //
                            // storage
                            } else if (step <= 3) {
                                setCurrentProgressStep(0);
                            // payload
                            } else if (step === 4) {
                                setCurrentProgressStep(1);
                            // configuration
                            } else if (step >= 5 && step <= 11) {
                                setCurrentProgressStep(2);
                            // bootloader
                            } else if (step >= 12) {
                                setCurrentProgressStep(3);
                            }
                            if (message) {
                                setStatusMessage(message);
                                refStatusMessage.current = message;
                            }
                        });
                        taskProxy.addEventListener("Failed", () => {
                            setStatus("danger");
                        });
                        taskProxy.addEventListener("Stopped", () => {
                            taskProxy.Finish().catch(onCritFail({
                                context: cockpit.format(N_("Installation of the system failed: $0"), refStatusMessage.current),
                            }));
                        });
                        taskProxy.addEventListener("Succeeded", () => {
                            setStatus("success");
                            setCurrentProgressStep(4);
                        });
                    };
                    taskProxy.wait(() => {
                        addEventListeners();
                        taskProxy.Start().catch(console.error);
                    });
                }, console.error);
    }, [onCritFail]);

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
        title = _("Successfully installed");
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
                      <Text>
                          {currentProgressStep < 4
                              ? progressSteps[currentProgressStep].description
                              : cockpit.format(_("To begin using $0, reboot your system."), osRelease.PRETTY_NAME)}
                      </Text>
                      {currentProgressStep < 4 && (
                          <>
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
                          </>)}
                  </Flex>
              }
              secondary={
                  status === "success" &&
                  <Button onClick={exitGui}>{isBootIso ? _("Reboot") : _("Quit")}</Button>
              }
              title={title}
              headingLevel="h2"
            />
        </Stack>
    );
};
