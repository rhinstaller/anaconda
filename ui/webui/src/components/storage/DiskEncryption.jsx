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
import React, { useState, useEffect } from "react";

import {
    Checkbox,
    EmptyState,
    EmptyStateHeader,
    EmptyStateIcon,
    EmptyStateFooter,
    Form,
    Spinner,
    TextContent,
    TextVariants,
    Text,
} from "@patternfly/react-core";

import "./DiskEncryption.scss";

import { PasswordFormFields, ruleLength } from "../Password.jsx";

const _ = cockpit.gettext;

const ruleAscii = {
    id: "ascii",
    text: (policy) => _("The passphrase you have provided contains non-ASCII characters. You may not be able to switch between keyboard layouts when typing it."),
    check: (policy, password) => password.length > 0 && /^[\x20-\x7F]*$/.test(password),
    isError: false,
};

export function getStorageEncryptionState (password = "", confirmPassword = "", encrypt = false) {
    return { password, confirmPassword, encrypt };
}

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
    passwordPolicies,
}) => {
    const [password, setPassword] = useState(storageEncryption.password);
    const [confirmPassword, setConfirmPassword] = useState(storageEncryption.confirmPassword);
    const isEncrypted = storageEncryption.encrypt;
    const luksPolicy = passwordPolicies.luks;

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
          policy={luksPolicy}
          initialPassword={password}
          passwordLabel={_("Passphrase")}
          initialConfirmPassword={confirmPassword}
          confirmPasswordLabel={_("Confirm passphrase")}
          rules={[ruleLength, ruleAscii]}
          onChange={setPassword}
          onConfirmChange={setConfirmPassword}
          setIsValid={setIsFormValid}
        />
    );

    useEffect(() => {
        setIsFormValid(!isEncrypted);
    }, [setIsFormValid, isEncrypted]);

    useEffect(() => {
        setStorageEncryption(se => ({ ...se, password }));
    }, [password, setStorageEncryption]);

    useEffect(() => {
        setStorageEncryption(se => ({ ...se, confirmPassword }));
    }, [confirmPassword, setStorageEncryption]);

    if (isInProgress) {
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
