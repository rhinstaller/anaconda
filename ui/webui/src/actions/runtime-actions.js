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

import {
    getPasswordPolicies,
} from "../apis/runtime.js";
import { setCriticalErrorAction } from "../actions/miscellaneous-actions.js";

export const getPasswordPoliciesAction = () => {
    return async (dispatch) => {
        try {
            const passwordPolicies = await getPasswordPolicies();

            return dispatch({
                type: "GET_RUNTIME_PASSWORD_POLICIES",
                payload: { passwordPolicies }
            });
        } catch (error) {
            setCriticalErrorAction(error);
        }
    };
};
