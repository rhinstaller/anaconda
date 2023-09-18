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
    ActionList,
    ActionListItem,
    Button,
    Divider,
    InputGroup,
    Flex,
    FlexItem,
    Form,
    FormGroup,
    Modal,
    Stack,
    StackItem,
    TextInput, InputGroupItem,
} from "@patternfly/react-core";
import { EyeIcon, EyeSlashIcon, LockIcon } from "@patternfly/react-icons";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { ModalError } from "cockpit-components-inline-notification.jsx";

import { getDevicesAction } from "../../actions/storage-actions.js";

import {
    unlockDevice,
} from "../../apis/storage.js";

const _ = cockpit.gettext;

export const EncryptedDevices = ({ dispatch, idPrefix, isLoadingNewPartitioning, lockedLUKSDevices, setSkipUnlock }) => {
    const [showUnlockDialog, setShowUnlockDialog] = useState(false);
    return (
        <>
            <Divider />
            <EmptyStatePanel
              title={_("Encrypted devices are locked")}
              paragraph={
                  <Stack hasGutter className={idPrefix + "-empty-state-body"}>
                      <StackItem>{_("Devices should be unlocked before assigning mount points.")}</StackItem>
                      <StackItem>
                          <Flex spaceItems={{ default: "spaceItemsLg" }}>
                              {lockedLUKSDevices.map(device => (
                                  <Flex key={device} spaceItems={{ default: "spaceItemsXs" }} alignItems={{ default: "alignItemsCenter" }}>
                                      <LockIcon />
                                      <FlexItem>{device}</FlexItem>
                                  </Flex>
                              ))}
                          </Flex>
                      </StackItem>
                  </Stack>
              }
              secondary={
                  <ActionList>
                      <ActionListItem>
                          <Button id={idPrefix + "-unlock-devices-btn"} variant="primary" onClick={() => setShowUnlockDialog(true)}>
                              {_("Unlock devices")}
                          </Button>
                      </ActionListItem>
                      <ActionListItem>
                          <Button variant="secondary" onClick={() => setSkipUnlock(true)}>
                              {_("Skip")}
                          </Button>
                      </ActionListItem>
                  </ActionList>
              }
            />
            <Divider />
            {showUnlockDialog &&
            <UnlockDialog
              dispatch={dispatch}
              isLoadingNewPartitioning={isLoadingNewPartitioning}
              onClose={() => setShowUnlockDialog(false)}
              lockedLUKSDevices={lockedLUKSDevices} />}
        </>
    );
};

const UnlockDialog = ({ isLoadingNewPartitioning, lockedLUKSDevices, onClose, dispatch }) => {
    const [password, setPassword] = useState("");
    const [passwordHidden, setPasswordHidden] = useState(true);
    const [dialogError, dialogErrorSet] = useState();
    const [inProgress, setInProgress] = useState(false);

    const onSubmit = () => {
        setInProgress(true);
        return Promise.allSettled(
            lockedLUKSDevices.map(device => (
                unlockDevice({ deviceName: device, passphrase: password })
            ))
        ).then(
            res => {
                if (res.every(r => r.status === "fulfilled")) {
                    // Blivet does not send a signal when a device is unlocked,
                    // so we need to refresh the device data manually.
                    dispatch(getDevicesAction());

                    if (res.every(r => r.value[0])) {
                        onClose();
                    } else {
                        dialogErrorSet(_("Incorrect passphrase"));
                        setInProgress(false);
                    }
                }
            },
            exc => {
                dialogErrorSet(exc.message);
                setInProgress(false);
            }
        );
    };

    return (
        <Modal
          id="unlock-device-dialog"
          position="top" variant="small" isOpen onClose={() => onClose()}
          title={_("Unlock encrypted devices")}
          description={_("All devices using this passphrase will be unlocked.")}
          footer={
              <>
                  <Button variant="primary" onClick={onSubmit} isDisabled={inProgress || isLoadingNewPartitioning} isLoading={inProgress} id="unlock-device-dialog-submit-btn">
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
                {dialogError && <ModalError dialogError={_("Some LUKS devices were not unlocked")} dialogErrorDetail={dialogError} />}
                <FormGroup fieldId="unlock-device-dialog-luks-password" label={_("Password")}>
                    <InputGroup>
                        <InputGroupItem isFill>
                            <TextInput
                              isRequired
                              id="unlock-device-dialog-luks-password"
                              type={passwordHidden ? "password" : "text"}
                              aria-label={_("Password")}
                              value={password}
                              onChange={(_event, val) => setPassword(val)}
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
                </FormGroup>
            </Form>
        </Modal>
    );
};
