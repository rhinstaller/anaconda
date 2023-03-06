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
import React, { useState } from "react";

import {
    ActionList,
    Button,
    Modal,
    ModalVariant,
    Stack,
    Tooltip,
    Wizard,
    WizardFooter,
    WizardContextConsumer,
} from "@patternfly/react-core";

import { InstallationDestination, applyDefaultStorage } from "./storage/InstallationDestination.jsx";
import { InstallationLanguage } from "./localization/InstallationLanguage.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration, ReviewConfigurationConfirmModal } from "./review/ReviewConfiguration.jsx";
import { exitGui } from "../helpers/exit.js";
import { usePageLocation } from "hooks";

const _ = cockpit.gettext;

export const AnacondaWizard = ({ onAddErrorNotification, toggleContextHelp, title }) => {
    const [isFormValid, setIsFormValid] = useState(true);
    const [stepNotification, setStepNotification] = useState();
    const [isInProgress, setIsInProgress] = useState(false);

    const stepsOrder = [
        {
            component: InstallationLanguage,
            id: "installation-language",
            label: _("Welcome"),
        },
        {
            component: InstallationDestination,
            id: "installation-destination",
            label: _("Installation destination"),
        },
        {
            component: ReviewConfiguration,
            id: "installation-review",
            label: _("Review and install"),
        },
        {
            component: InstallationProgress,
            id: "installation-progress",
        }
    ];

    const { path } = usePageLocation();
    const currentStepId = path[0] || "installation-language";
    const steps = stepsOrder.map((s, idx) => {
        return ({
            id: s.id,
            name: s.label,
            component: (
                <s.component
                  idPrefix={s.id}
                  setIsFormValid={setIsFormValid}
                  onAddErrorNotification={onAddErrorNotification}
                  toggleContextHelp={toggleContextHelp}
                  stepNotification={stepNotification}
                  isInProgress={isInProgress}
                />
            ),
            stepNavItemProps: { id: s.id },
            canJumpTo: idx <= stepsOrder.findIndex(s => s.id === currentStepId),
            isFinishedStep: idx === stepsOrder.length - 1
        });
    });

    const startAtStep = steps.findIndex(step => step.id === path[0]) + 1;
    const goToStep = (newStep) => {
        // first reset validation state to default
        setIsFormValid(true);

        cockpit.location.go([newStep.id]);
    };

    return (
        <Wizard
          id="installation-wizard"
          footer={<Footer
            isFormValid={isFormValid}
            setIsFormValid={setIsFormValid}
            setStepNotification={setStepNotification}
            isInProgress={isInProgress}
            setIsInProgress={setIsInProgress}
          />}
          hideClose
          mainAriaLabel={`${title} content`}
          navAriaLabel={`${title} steps`}
          onBack={goToStep}
          onGoToStep={goToStep}
          onNext={goToStep}
          startAtStep={startAtStep}
          steps={steps}
        />
    );
};

const Footer = ({ isFormValid, setIsFormValid, setStepNotification, isInProgress, setIsInProgress }) => {
    const [nextWaitsConfirmation, setNextWaitsConfirmation] = useState(false);
    const [quitWaitsConfirmation, setQuitWaitsConfirmation] = useState(false);

    const goToStep = (activeStep, onNext) => {
        // first reset validation state to default
        setIsFormValid(true);

        if (activeStep.id === "installation-destination") {
            setIsInProgress(true);

            applyDefaultStorage({
                onFail: ex => {
                    setIsInProgress(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    onNext();

                    // Reset the state after the onNext call. Otherwise,
                    // React will try to render the current step again.
                    setIsInProgress(false);
                    setStepNotification();
                }
            });
        } else if (activeStep.id === "installation-review") {
            setNextWaitsConfirmation(true);
        } else {
            onNext();
        }
    };

    if (isInProgress) {
        return null;
    }

    return (
        <WizardFooter>
            <WizardContextConsumer>
                {({ activeStep, onNext, onBack }) => {
                    const isBackDisabled = (
                        activeStep.id === "installation-language"
                    );
                    const nextButtonText = (
                        activeStep.id === "installation-review"
                            ? _("Erase disks and install")
                            : _("Next")
                    );
                    const nextButtonVariant = (
                        activeStep.id === "installation-review"
                            ? "warning"
                            : "primary"
                    );
                    return (
                        <Stack hasGutter>
                            {activeStep.id === "installation-review" &&
                            nextWaitsConfirmation &&
                            <ReviewConfigurationConfirmModal
                              idPrefix={activeStep.id}
                              onNext={onNext}
                              setNextWaitsConfirmation={setNextWaitsConfirmation}
                            />}
                            {quitWaitsConfirmation &&
                            <QuitInstallationConfirmModal
                              exitGui={exitGui}
                              setQuitWaitsConfirmation={setQuitWaitsConfirmation}
                            />}
                            <ActionList>
                                <Button
                                  variant="secondary"
                                  isDisabled={isBackDisabled}
                                  onClick={onBack}>
                                    {_("Back")}
                                </Button>
                                <Button
                                  id="installation-next-btn"
                                  aria-describedby="next-tooltip-ref"
                                  variant={nextButtonVariant}
                                  isDisabled={
                                      !isFormValid ||
                                      nextWaitsConfirmation
                                  }
                                  onClick={() => goToStep(activeStep, onNext)}>
                                    {nextButtonText}
                                </Button>
                                {activeStep.id === "installation-destination" &&
                                    <Tooltip
                                      id="next-tooltip-ref"
                                      content={
                                          <div>
                                              {_("To continue, select the devices(s) to install to.")}
                                          </div>
                                      }
                                      // Only show the tooltip on installation destination spoke that is not valid (no disks selected).
                                      // NOTE: As PatternFly Button with isDisabled set apprently does not get any mouse events anymore,
                                      //       we need to manually trigger the tooltip.
                                      reference={() => document.getElementById("installation-next-btn")}
                                      trigger="manual"
                                      isVisible={!isFormValid}
                                    />}
                                <Button
                                  id="installation-quit-btn"
                                  style={{ marginLeft: "var(--pf-c-wizard__footer-cancel--MarginLeft)" }}
                                  variant="link"
                                  onClick={() => {
                                      setQuitWaitsConfirmation(true);
                                  }}
                                >
                                    {_("Quit")}
                                </Button>
                            </ActionList>
                        </Stack>
                    );
                }}
            </WizardContextConsumer>
        </WizardFooter>
    );
};

export const QuitInstallationConfirmModal = ({ exitGui, setQuitWaitsConfirmation }) => {
    return (
        <Modal
          id="installation-quit-confirm-dialog"
          actions={[
              <Button
                id="installation-quit-confirm-btn"
                key="confirm"
                onClick={() => {
                    exitGui();
                }}
                variant="danger"
              >
                  {_("Quit")}
              </Button>,
              <Button
                id="installation-quit-confirm-cancel-btn"
                key="cancel"
                onClick={() => setQuitWaitsConfirmation(false)}
                variant="secondary">
                  {_("Continue installation")}
              </Button>
          ]}
          isOpen
          onClose={() => setQuitWaitsConfirmation(false)}
          title={_("Quit installer?")}
          titleIconVariant="warning"
          variant={ModalVariant.small}
        >
            {_("Your progress will not be saved.")}
        </Modal>
    );
};
