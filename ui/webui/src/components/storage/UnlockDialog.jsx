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
import React, { useState } from "react";

import {
    Button,
    InputGroup,
    Form,
    FormGroup,
    Modal,
    Text,
    TextContent,
    TextVariants,
    TextInput,
} from "@patternfly/react-core";
import { EyeIcon, EyeSlashIcon } from "@patternfly/react-icons";

import { ModalError } from "cockpit-components-inline-notification.jsx";

import { getDevicesAction } from "../../actions/storage-actions.js";

import {
    createPartitioning,
    unlockDevice,
} from "../../apis/storage.js";

const _ = cockpit.gettext;

export const UnlockDialog = ({ partition, onClose, dispatch }) => {
    const [password, setPassword] = useState("");
    const [passwordHidden, setPasswordHidden] = useState(true);
    const [dialogError, dialogErrorSet] = useState();
    const [inProgress, setInProgress] = useState(false);

    const onSubmit = () => {
        setInProgress(true);
        return unlockDevice({ deviceName: partition, passphrase: password })
                .then(
                    res => {
                        if (res[0]) {
                            // Blivet does not send a signal when a device is unlocked,
                            // so we need to refresh the device data manually.
                            dispatch(getDevicesAction());
                            // Also refresh the partitioning data which will now show the children
                            // of the unlocked device.
                            createPartitioning({ method: "MANUAL" });
                            onClose();
                        } else {
                            dialogErrorSet(_("Incorrect passphrase"));
                            setInProgress(false);
                        }
                    },
                    exc => {
                        dialogErrorSet(exc.message);
                        setInProgress(false);
                    });
    };

    return (
        <Modal
          id="unlock-device-dialog"
          position="top" variant="small" isOpen onClose={() => onClose()}
          title={cockpit.format(_("Unlock encrypted partition $0"), partition)}
          description={
              <TextContent>
                  <Text component={TextVariants.p}>{_("You need to unlock encrypted partitions before you can continue.")}</Text>
              </TextContent>
          }
          footer={
              <>
                  <Button variant="primary" onClick={onSubmit} isDisabled={inProgress} isLoading={inProgress} id="unlock-device-dialog-submit-btn">
                      {_("Unlock")}
                  </Button>
                  <Button variant="link" onClick={() => onClose()} id="unlock-device-dialog-cancel-btn">
                      {_("Cancel")}
                  </Button>
              </>
          }>
            <Form
              onSubmit={e => {
                  e.preventDefault();
                  onSubmit();
              }}>
                {dialogError && <ModalError dialogError={_("Failed to unlock LUKS partition")} dialogErrorDetail={dialogError} />}
                <FormGroup fieldId="unlock-device-dialog-luks-password" label={_("Password")}>
                    <InputGroup>
                        <TextInput
                          isRequired
                          id="unlock-device-dialog-luks-password"
                          type={passwordHidden ? "password" : "text"}
                          aria-label={_("Password")}
                          value={password}
                          onChange={setPassword}
                        />
                        <Button
                          variant="control"
                          onClick={() => setPasswordHidden(!passwordHidden)}
                          aria-label={passwordHidden ? _("Show password") : _("Hide password")}
                        >
                            {passwordHidden ? <EyeIcon /> : <EyeSlashIcon />}
                        </Button>
                    </InputGroup>
                </FormGroup>
            </Form>
        </Modal>
    );
};
