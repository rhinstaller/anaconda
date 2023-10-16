/*
 * Copyright (C) 2023 Red Hat, Inc.
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
import React, { useState, useEffect, useMemo } from "react";
import { debounce } from "throttle-debounce";

import {
    Button,
    Checkbox,
    EmptyState,
    EmptyStateIcon,
    Form,
    FormGroup,
    FormHelperText,
    HelperText,
    HelperTextItem,
    InputGroup,
    Spinner,
    TextInput,
    TextContent,
    TextVariants,
    Text, EmptyStateHeader, EmptyStateFooter, InputGroupItem,
} from "@patternfly/react-core";

// eslint-disable-next-line camelcase
import { password_quality } from "cockpit-components-password.jsx";
import EyeIcon from "@patternfly/react-icons/dist/esm/icons/eye-icon";
import EyeSlashIcon from "@patternfly/react-icons/dist/esm/icons/eye-slash-icon";
import ExclamationCircleIcon from "@patternfly/react-icons/dist/esm/icons/exclamation-circle-icon";
import ExclamationTriangleIcon from "@patternfly/react-icons/dist/esm/icons/exclamation-triangle-icon";
import CheckCircleIcon from "@patternfly/react-icons/dist/esm/icons/check-circle-icon";

import "./DiskEncryption.scss";

import { getPasswordPolicies } from "../../apis/runtime.js";

const _ = cockpit.gettext;

/* Calculate the password quality levels based on the password policy
 * If the policy specifies a 'is-strict' rule anything bellow the minimum specified by the policy
 * is considered invalid
 * @param {int} minQualility - the minimum quality level
 * @return {array} - the password strengh levels
 */
const getStrengthLevels = (minQualility, isStrict) => {
    const levels = [{
        id: "weak",
        label: _("Weak"),
        variant: "error",
        icon: <ExclamationCircleIcon />,
        lower_bound: 0,
        higher_bound: minQualility - 1,
        valid: !isStrict,
    }];

    if (minQualility <= 69) {
        levels.push({
            id: "medium",
            label: _("Medium"),
            variant: "warning",
            icon: <ExclamationTriangleIcon />,
            lower_bound: minQualility,
            higher_bound: 69,
            valid: true,
        });
    }

    levels.push({
        id: "strong",
        label: _("Strong"),
        variant: "success",
        icon: <CheckCircleIcon />,
        lower_bound: Math.max(70, minQualility),
        higher_bound: 100,
        valid: true,
    });

    return levels;
};

export function getStorageEncryptionState (password = "", confirmPassword = "", encrypt = false) {
    return { password, confirmPassword, encrypt };
}

const passwordStrengthLabel = (idPrefix, strength, strengthLevels) => {
    const level = strengthLevels.filter(l => l.id === strength)[0];
    if (level) {
        return (
            <HelperText>
                <HelperTextItem id={idPrefix + "-password-strength-label"} variant={level.variant} icon={level.icon}>
                    {level.label}
                </HelperTextItem>
            </HelperText>
        );
    }
};

// TODO create strengthLevels object with methods passed to the component ?
const PasswordFormFields = ({
    idPrefix,
    luksPolicies,
    password,
    passwordLabel,
    onChange,
    passwordConfirm,
    passwordConfirmLabel,
    onConfirmChange,
    passwordStrength,
    ruleLength,
    ruleConfirmMatches,
    ruleAscii,
    strengthLevels,
}) => {
    const [passwordHidden, setPasswordHidden] = useState(true);
    const [confirmHidden, setConfirmHidden] = useState(true);
    const [_password, _setPassword] = useState(password);
    const [_passwordConfirm, _setPasswordConfirm] = useState(passwordConfirm);

    useEffect(() => {
        debounce(300, () => onChange(_password))();
    }, [_password, onChange]);

    useEffect(() => {
        debounce(300, () => onConfirmChange(_passwordConfirm))();
    }, [_passwordConfirm, onConfirmChange]);

    return (
        <>
            <FormGroup
              label={passwordLabel}
              labelInfo={ruleLength === "success" && passwordStrengthLabel(idPrefix, passwordStrength, strengthLevels)}
            >
                <InputGroup>
                    <InputGroupItem isFill>
                        <TextInput
                          type={passwordHidden ? "password" : "text"}
                          value={_password}
                          onChange={(_event, val) => _setPassword(val)}
                          id={idPrefix + "-password-field"}
                        />
                    </InputGroupItem>
                    <InputGroupItem>
                        <Button
                          variant="control"
                          onClick={() => setPasswordHidden(!passwordHidden)}
                          aria-label={passwordHidden ? _("Show password") : _("Hide password")}
                        >
                            {passwordHidden ? <EyeIcon /> : <EyeSlashIcon />}
                        </Button>
                    </InputGroupItem>
                </InputGroup>
                <FormHelperText>
                    <HelperText component="ul" aria-live="polite" id={idPrefix + "-password-field-helper"}>
                        <HelperTextItem
                          id={idPrefix + "-password-rule-min-chars"}
                          isDynamic
                          variant={ruleLength}
                          component="li"
                        >
                            {cockpit.format(_("Must be at least $0 characters"), luksPolicies["min-length"].v)}
                        </HelperTextItem>
                        {ruleAscii &&
                        <HelperTextItem
                          id={idPrefix + "-password-rule-ascii"}
                          isDynamic
                          variant="warning"
                          component="li"
                        >
                            {_("The passphrase you have provided contains non-ASCII characters. You may not be able to switch between keyboard layouts when typing it.")}
                        </HelperTextItem>}
                    </HelperText>
                </FormHelperText>
            </FormGroup>
            <FormGroup
              label={passwordConfirmLabel}
            >
                <InputGroup>
                    <InputGroupItem isFill><TextInput
                      type={confirmHidden ? "password" : "text"}
                      value={_passwordConfirm}
                      onChange={(_event, val) => _setPasswordConfirm(val)}
                      id={idPrefix + "-password-confirm-field"}
                    />
                    </InputGroupItem>
                    <InputGroupItem>
                        <Button
                          variant="control"
                          onClick={() => setConfirmHidden(!confirmHidden)}
                          aria-label={confirmHidden ? _("Show confirmed password") : _("Hide confirmed password")}
                        >
                            {confirmHidden ? <EyeIcon /> : <EyeSlashIcon />}
                        </Button>
                    </InputGroupItem>
                </InputGroup>
                <FormHelperText>
                    <HelperText component="ul" aria-live="polite" id="password-confirm-field-helper">
                        <HelperTextItem
                          id={idPrefix + "-password-rule-match"}
                          isDynamic
                          variant={ruleConfirmMatches}
                          component="li"
                        >
                            {_("Passphrases must match")}
                        </HelperTextItem>
                    </HelperText>
                </FormHelperText>
            </FormGroup>
        </>
    );
};

const getPasswordStrength = async (password, strengthLevels) => {
    // In case of unacceptable password just return 0
    const force = true;
    const quality = await password_quality(password, force);
    const level = strengthLevels.filter(l => l.lower_bound <= quality.value && l.higher_bound >= quality.value)[0];
    return level.id;
};

const isValidStrength = (strength, strengthLevels) => {
    const level = strengthLevels.filter(l => l.id === strength)[0];

    return level ? level.valid : false;
};

const getRuleLength = (password, minLength) => {
    let ruleState = "indeterminate";
    if (password.length > 0 && password.length < minLength) {
        ruleState = "error";
    } else if (password.length >= minLength) {
        ruleState = "success";
    }
    return ruleState;
};

const getRuleConfirmMatches = (password, confirm) => (password.length > 0 ? (password === confirm ? "success" : "error") : "indeterminate");

const CheckDisksSpinner = (
    <EmptyState id="installation-destination-next-spinner">
        <EmptyStateHeader titleText={<>{_("Checking storage configuration")}</>} icon={<EmptyStateIcon icon={Spinner} />} headingLevel="h4" />
        <EmptyStateFooter>
            <TextContent>
                <Text component={TextVariants.p}>
                    {_("This may take a moment")}
                </Text>
            </TextContent>
        </EmptyStateFooter>
    </EmptyState>
);

export const DiskEncryption = ({
    idPrefix,
    isInProgress,
    setIsFormValid,
    storageEncryption,
    setStorageEncryption,
}) => {
    const [password, setPassword] = useState(storageEncryption.password);
    const [confirmPassword, setConfirmPassword] = useState(storageEncryption.confirmPassword);
    const [passwordStrength, setPasswordStrength] = useState("");
    const isEncrypted = storageEncryption.encrypt;
    const [luksPolicies, setLuksPolicies] = useState();

    useEffect(() => {
        getPasswordPolicies().then(policies => setLuksPolicies(policies.luks));
    }, []);

    const ruleConfirmMatches = useMemo(() => {
        return getRuleConfirmMatches(password, confirmPassword);
    }, [password, confirmPassword]);

    const ruleLength = useMemo(() => {
        return luksPolicies && getRuleLength(password, luksPolicies["min-length"].v);
    }, [password, luksPolicies]);

    const ruleAscii = useMemo(() => {
        return password.length > 0 && !/^[\x20-\x7F]*$/.test(password);
    }, [password]);

    const strengthLevels = useMemo(() => {
        return luksPolicies && getStrengthLevels(luksPolicies["min-quality"].v, luksPolicies["is-strict"].v);
    }, [luksPolicies]);

    const encryptedDevicesCheckbox = content => (
        <Checkbox
          id={idPrefix + "-encrypt-devices"}
          label={_("Encrypt my data")}
          isChecked={isEncrypted}
          onChange={(_event, encrypt) => setStorageEncryption(se => ({ ...se, encrypt }))}
          body={content}
        />
    );

    const passphraseForm = (
        <PasswordFormFields
          idPrefix={idPrefix}
          luksPolicies={luksPolicies}
          password={password}
          passwordLabel={_("Passphrase")}
          passwordStrength={passwordStrength}
          passwordConfirm={confirmPassword}
          passwordConfirmLabel={_("Confirm passphrase")}
          ruleLength={ruleLength}
          ruleConfirmMatches={ruleConfirmMatches}
          ruleAscii={ruleAscii}
          strengthLevels={strengthLevels}
          onChange={setPassword}
          onConfirmChange={setConfirmPassword}
        />
    );

    useEffect(() => {
        if (!strengthLevels) {
            return;
        }

        const updatePasswordStrength = async () => {
            const _passwordStrength = await getPasswordStrength(password, strengthLevels);
            setPasswordStrength(_passwordStrength);
        };
        updatePasswordStrength();
    }, [password, strengthLevels]);

    useEffect(() => {
        const updateValidity = (isEncrypted) => {
            const passphraseValid = (
                ruleLength === "success" &&
                ruleConfirmMatches === "success" &&
                isValidStrength(passwordStrength, strengthLevels)
            );
            setIsFormValid(!isEncrypted || passphraseValid);
        };

        updateValidity(isEncrypted);
    }, [setIsFormValid, isEncrypted, ruleConfirmMatches, ruleLength, passwordStrength, strengthLevels]);

    useEffect(() => {
        setStorageEncryption(se => ({ ...se, password }));
    }, [password, setStorageEncryption]);

    useEffect(() => {
        setStorageEncryption(se => ({ ...se, confirmPassword }));
    }, [confirmPassword, setStorageEncryption]);

    if (isInProgress || !luksPolicies) {
        return CheckDisksSpinner;
    }

    return (
        <>
            <TextContent>
                <Text component={TextVariants.p}>
                    {_("Encryption helps secure your data, to prevent others from accessing it.")}
                </Text>
                <Text component={TextVariants.p}>
                    {_("Only new partitions will be encrypted. Existing partitions will remain untouched.")}
                </Text>
            </TextContent>
            <Form>
                {encryptedDevicesCheckbox(isEncrypted ? passphraseForm : null)}
            </Form>
        </>
    );
};

export const getPageProps = ({ storageScenarioId }) => {
    return ({
        id: "disk-encryption",
        label: _("Disk encryption"),
        isHidden: storageScenarioId === "mount-point-mapping",
        title: _("Encrypt the selected devices?")
    });
};
