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
import React, { useState, useMemo } from "react";

import {
    ActionList,
    Button,
    HelperText,
    HelperTextItem,
    Modal,
    ModalVariant,
    PageSection,
    PageSectionTypes,
    PageSectionVariants,
    Stack,
    Wizard,
    WizardFooter,
    WizardContextConsumer,
} from "@patternfly/react-core";

import { InstallationMethod } from "./storage/InstallationMethod.jsx";
import { getScenario, getDefaultScenario } from "./storage/InstallationScenario.jsx";
import { MountPointMapping } from "./storage/MountPointMapping.jsx";
import { DiskEncryption, getStorageEncryptionState } from "./storage/DiskEncryption.jsx";
import { InstallationLanguage } from "./localization/InstallationLanguage.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration, ReviewConfigurationConfirmModal } from "./review/ReviewConfiguration.jsx";
import { exitGui } from "../helpers/exit.js";
import { debug } from "../helpers/log.js";
import { usePageLocation } from "hooks";
import {
    applyStorage,
    resetPartitioning,
} from "../apis/storage.js";

const _ = cockpit.gettext;

export const AnacondaWizard = ({ dispatch, isBootIso, osRelease, storageData, localizationData, onCritFail, onAddErrorNotification, title, conf }) => {
    const [isFormValid, setIsFormValid] = useState(true);
    const [stepNotification, setStepNotification] = useState();
    const [isInProgress, setIsInProgress] = useState(false);
    const [storageEncryption, setStorageEncryption] = useState(getStorageEncryptionState());
    const [storageScenarioId, setStorageScenarioId] = useState(window.sessionStorage.getItem("storage-scenario-id") || getDefaultScenario().id);
    const lastPartitioning = useMemo(() => {
        const lastPartitioningKey = Object.keys(storageData.partitioning || {}).find(path => parseInt(path.match(/\d+$/)[0]) === Object.keys(storageData.partitioning).length);

        return storageData.partitioning?.[lastPartitioningKey];
    }, [storageData.partitioning]);

    const language = useMemo(() => {
        for (const l of Object.keys(localizationData.languages)) {
            const locale = localizationData.languages[l].locales.find(locale => locale["locale-id"].v === localizationData.language);

            if (locale) {
                return locale;
            }
        }
    }, [localizationData]);
    const stepsOrder = [
        ...(isBootIso
            ? [{
                component: InstallationLanguage,
                data: { dispatch, languages: localizationData.languages, language: localizationData.language, commonLocales: localizationData.commonLocales },
                id: "installation-language",
                label: _("Welcome"),
            }]
            : []),
        {
            component: InstallationMethod,
            data: { deviceData: storageData.devices, diskSelection: storageData.diskSelection, dispatch },
            id: "installation-method",
            label: _("Installation method"),
        },
        {
            id: "disk-configuration",
            label: _("Disk configuration"),
            steps: [{
                component: MountPointMapping,
                data: { deviceData: storageData.devices, diskSelection: storageData.diskSelection, partitioningData: lastPartitioning, dispatch },
                id: "mount-point-mapping",
                label: _("Manual disk configuration"),
                isHidden: storageScenarioId !== "mount-point-mapping"

            }, {
                component: DiskEncryption,
                id: "disk-encryption",
                label: _("Disk encryption"),
                isHidden: storageScenarioId === "mount-point-mapping"
            }]
        },
        {
            component: ReviewConfiguration,
            data: {
                deviceData: storageData.devices,
                diskSelection: storageData.diskSelection,
                requests: lastPartitioning ? lastPartitioning.requests : null,
                language,
                osRelease
            },
            id: "installation-review",
            label: _("Review and install"),
        },
        {
            component: InstallationProgress,
            id: "installation-progress",
        }
    ];

    const getFlattenedStepsIds = (steps) => {
        const stepIds = [];
        for (const step of steps) {
            if (step.steps) {
                for (const childStep of step.steps) {
                    if (childStep?.isHidden !== true) {
                        stepIds.push(childStep.id);
                    }
                }
            } else {
                stepIds.push(step.id);
            }
        }
        return stepIds;
    };
    const flattenedStepsIds = getFlattenedStepsIds(stepsOrder);

    const { path } = usePageLocation();
    const currentStepId = isBootIso ? path[0] || "installation-language" : path[0] || "installation-method";

    const isFinishedStep = (stepId) => {
        const stepIdx = flattenedStepsIds.findIndex(s => s === stepId);
        return stepIdx === flattenedStepsIds.length - 1;
    };

    const canJumpToStep = (stepId, currentStepId) => {
        const stepIdx = flattenedStepsIds.findIndex(s => s === stepId);
        const currentStepIdx = flattenedStepsIds.findIndex(s => s === currentStepId);
        return stepIdx <= currentStepIdx;
    };

    const createSteps = (stepsOrder) => {
        const steps = stepsOrder.filter(s => !s.isHidden).map(s => {
            let step = ({
                id: s.id,
                name: s.label,
                stepNavItemProps: { id: s.id },
                canJumpTo: canJumpToStep(s.id, currentStepId),
                isFinishedStep: isFinishedStep(s.id),
            });
            if (s.component) {
                step = ({
                    ...step,
                    component: (
                        <s.component
                          idPrefix={s.id}
                          setIsFormValid={setIsFormValid}
                          onCritFail={onCritFail}
                          onAddErrorNotification={onAddErrorNotification}
                          stepNotification={stepNotification}
                          isInProgress={isInProgress}
                          storageEncryption={storageEncryption}
                          setStorageEncryption={setStorageEncryption}
                          storageScenarioId={storageScenarioId}
                          isBootIso={isBootIso}
                          osRelease={osRelease}
                          setStorageScenarioId={(scenarioId) => {
                              window.sessionStorage.setItem("storage-scenario-id", scenarioId);
                              setStorageScenarioId(scenarioId);
                          }}
                          {...s.data}
                        />
                    ),
                });
            } else if (s.steps) {
                step.steps = createSteps(s.steps);
            }
            return step;
        });
        return steps;
    };
    const steps = createSteps(stepsOrder);

    const goToStep = (newStep) => {
        // first reset validation state to default
        setIsFormValid(false);

        cockpit.location.go([newStep.id]);
    };

    return (
        <PageSection type={PageSectionTypes.wizard} variant={PageSectionVariants.light}>
            <Wizard
              id="installation-wizard"
              footer={<Footer
                onCritFail={onCritFail}
                isFormValid={isFormValid}
                partitioning={lastPartitioning?.path}
                setIsFormValid={setIsFormValid}
                setStepNotification={setStepNotification}
                isInProgress={isInProgress}
                setIsInProgress={setIsInProgress}
                storageEncryption={storageEncryption}
                storageScenarioId={storageScenarioId}
                isBootIso={isBootIso}
              />}
              hideClose
              mainAriaLabel={`${title} content`}
              navAriaLabel={`${title} steps`}
              onBack={goToStep}
              onGoToStep={goToStep}
              onNext={goToStep}
              steps={steps}
              isNavExpandable
            />
        </PageSection>
    );
};

const Footer = ({
    onCritFail,
    isFormValid,
    setIsFormValid,
    setStepNotification,
    isInProgress,
    partitioning,
    setIsInProgress,
    storageEncryption,
    storageScenarioId,
    isBootIso
}) => {
    const [nextWaitsConfirmation, setNextWaitsConfirmation] = useState(false);
    const [quitWaitsConfirmation, setQuitWaitsConfirmation] = useState(false);

    const goToNextStep = (activeStep, onNext) => {
        // first reset validation state to default
        setIsFormValid(true);

        if (activeStep.id === "disk-encryption") {
            setIsInProgress(true);

            applyStorage({
                onFail: ex => {
                    console.error(ex);
                    setIsInProgress(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    onNext();

                    // Reset the state after the onNext call. Otherwise,
                    // React will try to render the current step again.
                    setIsInProgress(false);
                    setStepNotification();
                },
                encrypt: storageEncryption.encrypt,
                encryptPassword: storageEncryption.password,
            });
        } else if (activeStep.id === "installation-review") {
            setNextWaitsConfirmation(true);
        } else if (activeStep.id === "mount-point-mapping") {
            setIsInProgress(true);

            applyStorage({
                partitioning,
                onFail: ex => {
                    console.error(ex);
                    setIsInProgress(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    onNext();

                    // Reset the state after the onNext call. Otherwise,
                    // React will try to render the current step again.
                    setIsInProgress(false);
                    setStepNotification();
                },
            });
        } else {
            onNext();
        }
    };

    const goToPreviousStep = (activeStep, onBack, errorHandler) => {
        // first reset validation state to default
        setIsFormValid(true);
        onBack();
        if (activeStep.id === "installation-review") {
            resetPartitioning().then(() => {
                debug("resetPartitioning");
            }, errorHandler);
        }
    };

    if (isInProgress) {
        return null;
    }

    return (
        <WizardFooter>
            <WizardContextConsumer>
                {({ activeStep, onNext, onBack }) => {
                    const isFirstScreen = (
                        activeStep.id === "installation-language" || (activeStep.id === "installation-method" && !isBootIso)
                    );
                    const nextButtonText = (
                        activeStep.id === "installation-review"
                            ? getScenario(storageScenarioId).buttonLabel
                            : _("Next")
                    );
                    const nextButtonVariant = (
                        activeStep.id === "installation-review"
                            ? "warning"
                            : "primary"
                    );

                    const reviewWarning = getScenario(storageScenarioId).screenWarning;

                    return (
                        <Stack hasGutter>
                            {activeStep.id === "installation-review" &&
                            nextWaitsConfirmation &&
                            <ReviewConfigurationConfirmModal
                              idPrefix={activeStep.id}
                              onNext={onNext}
                              setNextWaitsConfirmation={setNextWaitsConfirmation}
                              storageScenarioId={storageScenarioId}
                            />}
                            {quitWaitsConfirmation &&
                            <QuitInstallationConfirmModal
                              exitGui={exitGui}
                              setQuitWaitsConfirmation={setQuitWaitsConfirmation}
                              isBootIso={isBootIso}
                            />}
                            {activeStep.id === "installation-method" && !isFormValid &&
                                <HelperText id="next-helper-text">
                                    <HelperTextItem
                                      variant="indeterminate">
                                        {_("To continue, select the devices to install to.")}
                                    </HelperTextItem>
                                </HelperText>}
                            {activeStep.id === "installation-review" && reviewWarning &&
                                <HelperText id="review-warning-text">
                                    <HelperTextItem
                                      variant="warning"
                                      hasIcon>
                                        {reviewWarning}
                                    </HelperTextItem>
                                </HelperText>}
                            <ActionList>
                                <Button
                                  id="installation-back-btn"
                                  variant="secondary"
                                  isDisabled={isFirstScreen}
                                  onClick={() => goToPreviousStep(
                                      activeStep,
                                      onBack,
                                      onCritFail({ context: cockpit.format(_("Go back from $0"), activeStep.name) })
                                  )}>
                                    {_("Back")}
                                </Button>
                                <Button
                                  id="installation-next-btn"
                                  variant={nextButtonVariant}
                                  isDisabled={
                                      !isFormValid ||
                                      nextWaitsConfirmation
                                  }
                                  onClick={() => goToNextStep(activeStep, onNext)}>
                                    {nextButtonText}
                                </Button>
                                <Button
                                  id="installation-quit-btn"
                                  style={{ marginLeft: "var(--pf-c-wizard__footer-cancel--MarginLeft)" }}
                                  variant="link"
                                  onClick={() => {
                                      setQuitWaitsConfirmation(true);
                                  }}
                                >
                                    {isBootIso ? _("Reboot") : _("Quit")}
                                </Button>
                            </ActionList>
                        </Stack>
                    );
                }}
            </WizardContextConsumer>
        </WizardFooter>
    );
};

export const QuitInstallationConfirmModal = ({ exitGui, setQuitWaitsConfirmation, isBootIso }) => {
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
                  {isBootIso ? _("Reboot") : _("Quit")}
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
          title={isBootIso ? _("Reboot system?") : _("Quit installer?")}
          titleIconVariant="warning"
          variant={ModalVariant.small}
        >
            {_("Your progress will not be saved.")}
        </Modal>
    );
};
