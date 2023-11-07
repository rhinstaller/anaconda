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
import React, { useContext, useEffect, useState, useMemo } from "react";

import {
    ActionList,
    Button,
    Modal,
    ModalVariant,
    PageSection,
    PageSectionTypes,
    PageSectionVariants,
    Stack
} from "@patternfly/react-core";
import {
    Wizard,
    WizardFooter,
    WizardContextConsumer
} from "@patternfly/react-core/deprecated";

import { AnacondaPage } from "./AnacondaPage.jsx";
import { InstallationMethod, getPageProps as getInstallationMethodProps } from "./storage/InstallationMethod.jsx";
import { getDefaultScenario } from "./storage/InstallationScenario.jsx";
import { MountPointMapping, getPageProps as getMountPointMappingProps } from "./storage/MountPointMapping.jsx";
import { DiskEncryption, getStorageEncryptionState, getPageProps as getDiskEncryptionProps } from "./storage/DiskEncryption.jsx";
import { InstallationLanguage, getPageProps as getInstallationLanguageProps } from "./localization/InstallationLanguage.jsx";
import { Accounts, getPageProps as getAccountsProps, getAccountsState, accountsToDbusUsers } from "./users/Accounts.jsx";
import { InstallationProgress } from "./installation/InstallationProgress.jsx";
import { ReviewConfiguration, ReviewConfigurationConfirmModal, getPageProps as getReviewConfigurationProps } from "./review/ReviewConfiguration.jsx";
import { exitGui } from "../helpers/exit.js";
import { usePageLocation } from "hooks";
import {
    getRequiredMountPoints,
} from "../apis/storage_devicetree.js";
import {
    applyStorage,
    resetPartitioning,
} from "../apis/storage_partitioning.js";
import {
    setUsers,
} from "../apis/users.js";
import { SystemTypeContext, OsReleaseContext } from "./Common.jsx";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

export const AnacondaWizard = ({ dispatch, storageData, localizationData, runtimeData, onCritFail, title, conf }) => {
    const [isFormDisabled, setIsFormDisabled] = useState(false);
    const [isFormValid, setIsFormValid] = useState(false);
    const [requiredMountPoints, setRequiredMountPoints] = useState();
    const [reusePartitioning, setReusePartitioning] = useState(false);
    const [stepNotification, setStepNotification] = useState();
    const [storageEncryption, setStorageEncryption] = useState(getStorageEncryptionState());
    const [storageScenarioId, setStorageScenarioId] = useState(window.sessionStorage.getItem("storage-scenario-id") || getDefaultScenario().id);
    const [accounts, setAccounts] = useState(getAccountsState());
    const [showWizard, setShowWizard] = useState(true);
    const osRelease = useContext(OsReleaseContext);
    const isBootIso = useContext(SystemTypeContext) === "BOOT_ISO";

    const availableDevices = useMemo(() => {
        return Object.keys(storageData.devices);
    }, [storageData.devices]);

    useEffect(() => {
        const updateRequiredMountPoints = async () => {
            const requiredMountPoints = await getRequiredMountPoints().catch(console.error);

            setRequiredMountPoints(requiredMountPoints);
        };
        updateRequiredMountPoints();
    }, []);

    useEffect(() => {
        /*
         * When disk selection changes or the user re-scans the devices we need to re-create the partitioning.
         * For Automatic partitioning we do it each time we go to review page,
         * but for custom mount assignment we try to reuse the partitioning when possible.
         */
        setReusePartitioning(false);
    }, [availableDevices, storageData.diskSelection.selectedDisks]);

    const language = useMemo(() => {
        for (const l of Object.keys(localizationData.languages)) {
            const locale = localizationData.languages[l].locales.find(locale => locale["locale-id"].v === localizationData.language);

            if (locale) {
                return locale;
            }
        }
    }, [localizationData]);
    const stepsOrder = [
        {
            component: InstallationLanguage,
            data: { dispatch, languages: localizationData.languages, language: localizationData.language, commonLocales: localizationData.commonLocales },
            ...getInstallationLanguageProps({ isBootIso, osRelease })
        },
        {
            component: InstallationMethod,
            data: {
                deviceData: storageData.devices,
                diskSelection: storageData.diskSelection,
                dispatch,
                storageScenarioId,
                setStorageScenarioId: (scenarioId) => {
                    window.sessionStorage.setItem("storage-scenario-id", scenarioId);
                    setStorageScenarioId(scenarioId);
                }
            },
            ...getInstallationMethodProps({ isBootIso, osRelease, isFormValid })
        },
        {
            id: "disk-configuration",
            label: _("Disk configuration"),
            steps: [{
                component: MountPointMapping,
                data: {
                    deviceData: storageData.devices,
                    diskSelection: storageData.diskSelection,
                    dispatch,
                    partitioningData: storageData.partitioning,
                    requiredMountPoints,
                    reusePartitioning,
                    setReusePartitioning,
                },
                ...getMountPointMappingProps({ storageScenarioId })
            }, {
                component: DiskEncryption,
                data: {
                    storageEncryption,
                    setStorageEncryption,
                    passwordPolicies: runtimeData.passwordPolicies,
                },
                ...getDiskEncryptionProps({ storageScenarioId })
            }]
        },
        {
            component: Accounts,
            data: {
                accounts,
                setAccounts,
                passwordPolicies: runtimeData.passwordPolicies,
            },
            ...getAccountsProps({ isBootIso })
        },
        {
            component: ReviewConfiguration,
            data: {
                deviceData: storageData.devices,
                diskSelection: storageData.diskSelection,
                requests: storageData.partitioning ? storageData.partitioning.requests : null,
                language,
                localizationData,
                storageScenarioId,
                accounts,
            },
            ...getReviewConfigurationProps({ storageScenarioId })
        },
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
    const firstStepId = stepsOrder.filter(step => !step.isHidden)[0].id;
    const currentStepId = path[0] || firstStepId;

    const isStepFollowedBy = (earlierStepId, laterStepId) => {
        const earlierStepIdx = flattenedStepsIds.findIndex(s => s === earlierStepId);
        const laterStepIdx = flattenedStepsIds.findIndex(s => s === laterStepId);
        return earlierStepIdx < laterStepIdx;
    };

    const canJumpToStep = (stepId, currentStepId) => {
        return stepId === currentStepId || isStepFollowedBy(stepId, currentStepId);
    };

    const createSteps = (stepsOrder) => {
        const steps = stepsOrder.filter(s => !s.isHidden).map(s => {
            let step = ({
                id: s.id,
                name: s.label,
                stepNavItemProps: { id: s.id },
                canJumpTo: canJumpToStep(s.id, currentStepId),
            });
            if (s.component) {
                step = ({
                    ...step,
                    component: (
                        <AnacondaPage step={s.id} title={s.title} stepNotification={stepNotification}>
                            <s.component
                              idPrefix={s.id}
                              setIsFormValid={setIsFormValid}
                              onCritFail={onCritFail}
                              setStepNotification={ex => setStepNotification({ step: s.id, ...ex })}
                              isFormDisabled={isFormDisabled}
                              setIsFormDisabled={setIsFormDisabled}
                              {...s.data}
                            />
                        </AnacondaPage>
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

    const goToStep = (newStep, prevStep) => {
        if (prevStep.prevId !== newStep.id) {
            // first reset validation state to default
            setIsFormValid(false);
        }

        // Reset the applied partitioning when going back from a step after creating partitioning to a step
        // before creating partitioning.
        if ((prevStep.prevId === "accounts" || isStepFollowedBy("accounts", prevStep.prevId)) &&
            isStepFollowedBy(newStep.id, "accounts")) {
            setIsFormDisabled(true);
            resetPartitioning()
                    .then(
                        () => cockpit.location.go([newStep.id]),
                        () => onCritFail({ context: cockpit.format(N_("Error was hit when going back from $0."), prevStep.prevName) })
                    )
                    .always(() => setIsFormDisabled(false));
        } else {
            cockpit.location.go([newStep.id]);
        }
    };

    if (!showWizard) {
        return (
            <PageSection variant={PageSectionVariants.light}>
                <InstallationProgress onCritFail={onCritFail} />
            </PageSection>
        );
    }

    return (
        <PageSection type={PageSectionTypes.wizard} variant={PageSectionVariants.light}>
            <Wizard
              id="installation-wizard"
              footer={<Footer
                onCritFail={onCritFail}
                isFormValid={isFormValid}
                partitioning={storageData.partitioning?.path}
                setIsFormValid={setIsFormValid}
                setStepNotification={setStepNotification}
                isFormDisabled={isFormDisabled}
                setIsFormDisabled={setIsFormDisabled}
                setShowWizard={setShowWizard}
                stepsOrder={stepsOrder}
                storageEncryption={storageEncryption}
                storageScenarioId={storageScenarioId}
                accounts={accounts}
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
    isFormDisabled,
    partitioning,
    setIsFormDisabled,
    setShowWizard,
    stepsOrder,
    storageEncryption,
    storageScenarioId,
    accounts,
}) => {
    const [nextWaitsConfirmation, setNextWaitsConfirmation] = useState(false);
    const [quitWaitsConfirmation, setQuitWaitsConfirmation] = useState(false);
    const isBootIso = useContext(SystemTypeContext) === "BOOT_ISO";

    const goToNextStep = (activeStep, onNext) => {
        // first reset validation state to default
        setIsFormValid(true);

        if (activeStep.id === "disk-encryption") {
            setIsFormDisabled(true);

            applyStorage({
                onFail: ex => {
                    console.error(ex);
                    setIsFormDisabled(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    onNext();

                    // Reset the state after the onNext call. Otherwise,
                    // React will try to render the current step again.
                    setIsFormDisabled(false);
                    setStepNotification();
                },
                encrypt: storageEncryption.encrypt,
                encryptPassword: storageEncryption.password,
            });
        } else if (activeStep.id === "installation-review") {
            setNextWaitsConfirmation(true);
        } else if (activeStep.id === "mount-point-mapping") {
            setIsFormDisabled(true);

            applyStorage({
                partitioning,
                onFail: ex => {
                    console.error(ex);
                    setIsFormDisabled(false);
                    setStepNotification({ step: activeStep.id, ...ex });
                },
                onSuccess: () => {
                    onNext();

                    // Reset the state after the onNext call. Otherwise,
                    // React will try to render the current step again.
                    setIsFormDisabled(false);
                    setStepNotification();
                },
            });
        } else if (activeStep.id === "accounts") {
            setUsers(accountsToDbusUsers(accounts));
            onNext();
        } else {
            onNext();
        }
    };

    const goToPreviousStep = (activeStep, onBack, errorHandler) => {
        // first reset validation state to default
        setIsFormValid(true);
        onBack();
    };

    return (
        <WizardFooter>
            <WizardContextConsumer>
                {({ activeStep, onNext, onBack }) => {
                    const currentStep = stepsOrder.find(s => s.id === activeStep.id);
                    const footerHelperText = currentStep?.footerHelperText;
                    const isFirstScreen = stepsOrder.filter(step => !step.isHidden)[0].id === activeStep.id;
                    const nextButtonText = currentStep?.nextButtonText || _("Next");
                    const nextButtonVariant = currentStep?.nextButtonVariant || "primary";

                    return (
                        <Stack hasGutter>
                            {activeStep.id === "installation-review" &&
                            nextWaitsConfirmation &&
                            <ReviewConfigurationConfirmModal
                              idPrefix={activeStep.id}
                              onNext={() => { setShowWizard(false); cockpit.location.go(["installation-progress"]) }}
                              setNextWaitsConfirmation={setNextWaitsConfirmation}
                              storageScenarioId={storageScenarioId}
                            />}
                            {quitWaitsConfirmation &&
                            <QuitInstallationConfirmModal
                              exitGui={exitGui}
                              setQuitWaitsConfirmation={setQuitWaitsConfirmation}
                            />}
                            {footerHelperText}
                            <ActionList>
                                <Button
                                  id="installation-back-btn"
                                  variant="secondary"
                                  isDisabled={isFirstScreen || isFormDisabled}
                                  onClick={() => goToPreviousStep(
                                      activeStep,
                                      onBack,
                                      onCritFail({ context: cockpit.format(N_("Error was hit when going back from $0."), activeStep.name) })
                                  )}>
                                    {_("Back")}
                                </Button>
                                <Button
                                  id="installation-next-btn"
                                  variant={nextButtonVariant}
                                  isDisabled={
                                      !isFormValid ||
                                      isFormDisabled ||
                                      nextWaitsConfirmation
                                  }
                                  onClick={() => goToNextStep(activeStep, onNext)}>
                                    {nextButtonText}
                                </Button>
                                <Button
                                  id="installation-quit-btn"
                                  isDisabled={isFormDisabled}
                                  style={{ marginLeft: "var(--pf-v5-c-wizard__footer-cancel--MarginLeft)" }}
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

export const QuitInstallationConfirmModal = ({ exitGui, setQuitWaitsConfirmation }) => {
    const isBootIso = useContext(SystemTypeContext) === "BOOT_ISO";

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
