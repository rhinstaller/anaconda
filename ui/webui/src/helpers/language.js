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

/*
 * Converts a language locale ID to a string that a Cockpit language cookie expects:
 * The expected format can be found here https://github.com/cockpit-project/cockpit/blob/main/po/language_map.txt
 */
export const convertToCockpitLang = ({ lang }) => {
    return lang.split(".UTF-8")[0].replace(/_/g, "-").toLowerCase();
};

export const setLangCookie = ({ cockpitLang }) => {
    const cookie = "CockpitLang=" + encodeURIComponent(cockpitLang) + "; path=/; expires=Sun, 16 Jul 3567 06:23:41 GMT";
    document.cookie = cookie;
    window.localStorage.setItem("cockpit.lang", cockpitLang);
};
