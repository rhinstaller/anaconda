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

import React, { useContext, useState } from "react";

import {
    ActionList,
    Alert,
    Button,
    Modal,
    ModalVariant,
    Stack,
    TextContent,
    Title,
    Wizard,
    WizardFooter,
    WizardContextConsumer,
} from "@patternfly/react-core";

import { AddressContext } from "./Common.jsx";
import { InstallationDestination, applyDefaultStorage } from "./storage/InstallationDestination.jsx";
import { InstallationLanguage } from "./localization/InstallationLanguage.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration, ReviewConfigurationConfirmModal } from "./review/ReviewConfiguration.jsx";

import { exitGui } from "../helpers/exit.js";

import { usePageLocation } from "hooks";

const _ = cockpit.gettext;

const getSteps = ({
    address,
    currentStepId,
    onAddErrorNotification,
    setIsFormValid,
    stepNotification,
    stepsOrder
}) => {
    const wrapWithContext = (children, label) => {
        return (
            <Stack hasGutter>
                <TextContent>
                    <Title headingLevel="h2">
                        {label}
                    </Title>
                    {stepNotification &&
                     (stepNotification.step === currentStepId) &&
                     <Alert
                       isInline
                       title={stepNotification.message}
                       variant="danger"
                     />}
                    {children}
                </TextContent>
            </Stack>
        );
    };

    return stepsOrder.map((s, idx) => {
        const Renderer = s.component;

        return ({
            id: s.id,
            name: s.label,
            component: wrapWithContext(
                <Renderer
                  idPrefix={s.id}
                  setIsFormValid={setIsFormValid}
                  onAddErrorNotification={onAddErrorNotification} />,
                s.title || s.label
            ),
            stepNavItemProps: { id: s.id },
            canJumpTo: idx <= stepsOrder.findIndex(s => s.id === currentStepId),
            isFinishedStep: idx === stepsOrder.length - 1
        });
    });
};

export const AnacondaWizard = ({ onAddErrorNotification, title }) => {
    const [isFormValid, setIsFormValid] = useState(true);

    const stepsOrder = [
        {
            component: InstallationLanguage,
            id: "installation-language",
            label: _("Welcome"),
            title: _("Welcome to the Anaconda installer")
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

    const address = useContext(AddressContext);
    const { path } = usePageLocation();
    const currentStepId = path[0] || "installation-language";

    const [stepNotification, setStepNotification] = useState();

    const steps = getSteps({
        address,
        currentStepId,
        setIsFormValid,
        onAddErrorNotification,
        stepNotification,
        stepsOrder
    });
    const startAtStep = steps.findIndex(step => step.id === path[0]) + 1;
    const goToStep = (newStep) => {
        cockpit.location.go([newStep.id]);
    };

    return (
        <Wizard
          footer={<Footer isFormValid={isFormValid} setStepNotification={setStepNotification} />}
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

const Footer = ({ isFormValid, setStepNotification }) => {
    const [isInProgress, setIsInProgress] = useState(false);
    const [nextWaitsConfirmation, setNextWaitsConfirmation] = useState(false);
    const [quitWaitsConfirmation, setQuitWaitsConfirmation] = useState(false);

    const goToStep = (activeStep, onNext) => {
        if (activeStep.id === "installation-destination") {
            setIsInProgress(true);

            applyDefaultStorage({
                onFail: ex => {
                    setIsInProgress(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    setIsInProgress(false);
                    setStepNotification();
                    onNext();
                }
            });
        } else if (activeStep.id === "installation-review") {
            setNextWaitsConfirmation(true);
        } else {
            onNext();
        }
    };

    return (
        <WizardFooter>
            <WizardContextConsumer>
                {({ activeStep, onNext, onBack }) => {
                    const isBackDisabled = (
                        activeStep.id === "installation-language"
                    );
                    const nextButtonText = (
                        activeStep.id === "installation-review"
                            ? _("Begin installation")
                            : _("Next")
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
                                  variant="primary"
                                  isDisabled={
                                      !isFormValid ||
                                      isInProgress ||
                                      nextWaitsConfirmation
                                  }
                                  isLoading={isInProgress}
                                  onClick={() => goToStep(activeStep, onNext)}>
                                    {nextButtonText}
                                </Button>
                                <Button
                                  variant="secondary"
                                  isDisabled={isBackDisabled}
                                  onClick={onBack}>
                                    {_("Back")}
                                </Button>
                                <Button
                                  id="installation-quit-btn"
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
