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
    Alert,
    Button,
    Title,
    Stack,
    Wizard, WizardFooter, WizardContextConsumer,
} from "@patternfly/react-core";

import { AddressContext } from "./Common.jsx";
import { InstallationDestination, applyDefaultStorage } from "./storage/InstallationDestination.jsx";
import { InstallationLanguage } from "./installation/InstallationLanguage.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration } from "./installation/ReviewConfiguration.jsx";

import { exitGui } from "../helpers/exit.js";

import { usePageLocation } from "hooks";

const _ = cockpit.gettext;

const getSteps = ({ address, currentStepId, onAddErrorNotification, stepNotification, stepsOrder, stepsVisited }) => {
    const wrapWithContext = (children, label) => {
        return (
            <Stack hasGutter>
                <Title headingLevel="h2" size="xl">
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
            </Stack>
        );
    };

    return stepsOrder.map((s, idx) => {
        const Renderer = s.component;

        return ({
            id: s.id,
            name: s.label,
            component: wrapWithContext(<Renderer onAddErrorNotification={onAddErrorNotification} />, s.label),
            stepNavItemProps: { id: s.id },
            canJumpTo: idx === 0 ? currentStepId === s.id : stepsVisited.includes(s.id),
            isFinishedStep: idx === stepsOrder.length - 1
        });
    });
};

export const AnacondaWizard = ({ onAddErrorNotification, title }) => {
    const stepsOrder = [
        {
            component: InstallationLanguage,
            id: "installation-language",
            label: _("Installation language"),
        },
        {
            component: InstallationDestination,
            id: "installation-destination",
            label: _("Storage configuration"),
        },
        {
            component: ReviewConfiguration,
            id: "review-configuration",
            label: _("Review"),
        },
        {
            component: InstallationProgress,
            id: "installation-progress",
            label: _("Installation progress"),
        }
    ];

    const address = useContext(AddressContext);
    const { path } = usePageLocation();
    const currentStepId = path[0] || "installation-language";

    const [stepNotification, setStepNotification] = useState();
    const [stepsVisited, setStepsVisited] = useState(
        stepsOrder.slice(0, stepsOrder.findIndex(step => step.id === currentStepId) + 1)
                .map(step => step.id)
    );

    const steps = getSteps({ address, currentStepId, onAddErrorNotification, stepNotification, stepsOrder, stepsVisited });
    const startAtStep = steps.findIndex(step => step.id === path[0]) + 1;
    const goToStep = (newStep) => {
        setStepsVisited([...stepsVisited, newStep.id]);

        cockpit.location.go([newStep.id]);
    };

    return (
        <Wizard
          footer={<Footer setStepNotification={setStepNotification} />}
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

const Footer = ({ setStepNotification }) => {
    const [isInProgress, setIsInProgress] = useState(false);

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
        } else {
            onNext();
        }
    };

    return (
        <WizardFooter>
            <WizardContextConsumer>
                {({ activeStep, onNext, onBack }) => {
                    const isBackDisabled = (
                        activeStep.id === "installation-destination" ||
                        activeStep.id === "installation-language"
                    );
                    const nextButtonText = (
                        activeStep.id === "review-configuration"
                            ? _("Begin installation")
                            : _("Next")
                    );

                    return (
                        <>
                            <Button
                              variant="primary"
                              isDisabled={isInProgress}
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
                            <Button variant="link" onClick={exitGui}>
                                {_("Quit")}
                            </Button>
                        </>
                    );
                }}
            </WizardContextConsumer>
        </WizardFooter>
    );
};
