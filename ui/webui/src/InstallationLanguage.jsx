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

import React, { useContext, useState } from "react";
import cockpit from "cockpit";

import {
    ActionGroup,
    Button,
    Form, FormGroup,
    Menu, MenuContent, MenuList, MenuInput, MenuItem, Divider, DrilldownMenu,
    PageSection,
    TextInput, Title,
} from "@patternfly/react-core";

import { AddressContext } from "./Common.jsx";

import { useEvent, useObject } from "hooks";

import "./InstallationLanguage.scss";

const _ = cockpit.gettext;

const LanguageSelector = ({ onSelectLang }) => {
    const [activeItem, setActiveItem] = useState();
    const [activeMenu, setActiveMenu] = useState("languageMenu");
    const [drilldownPath, setDrilldownPath] = useState([]);
    const [filterText, setFilterText] = useState("");
    const [menuDrilledIn, setMenuDrilledIn] = useState([]);
    const [selectedItem, setSelectedItem] = useState();
    const [languages, setLanguages] = useState([]);
    const [locales, setLocales] = useState({});
    const address = useContext(AddressContext);

    const localizationProxy = useObject(() => {
        const client = cockpit.dbus("org.fedoraproject.Anaconda.Modules.Localization", { superuser: "try", bus: "none", address });
        const proxy = client.proxy(
            "org.fedoraproject.Anaconda.Modules.Localization",
            "/org/fedoraproject/Anaconda/Modules/Localization",
        );

        return proxy;
    }, null, [address]);

    useEvent(localizationProxy, "changed", (event, data) => {
        localizationProxy.GetLanguages().then(languages => {
            // Create the languages state object
            Promise.all(languages.map(lang => localizationProxy.GetLanguageData(lang))).then(setLanguages);

            // Create the locales state object
            Promise.all(languages.map(lang => localizationProxy.GetLocales(lang))).then(res => {
                return Promise.all(
                    res.map((langLocales) => {
                        return Promise.all(langLocales.map(locale => localizationProxy.GetLocaleData(locale)));
                    })
                );
            })
                    .then(res => {
                        setLocales(res.reduce((a, v) => ({ ...a, [v[0]["language-id"].v]: v }), {}));
                    });
        });
    });

    const handleDrillIn = (fromMenuId, toMenuId, pathId) => {
        setMenuDrilledIn([...menuDrilledIn, fromMenuId]);
        setDrilldownPath([...drilldownPath, pathId]);
        setActiveMenu(toMenuId);
    };
    const handleDrillOut = toMenuId => {
        const menuDrilledInSansLast = menuDrilledIn.slice(0, menuDrilledIn.length - 1);
        const pathSansLast = drilldownPath.slice(0, drilldownPath.length - 1);

        setMenuDrilledIn(menuDrilledInSansLast);
        setDrilldownPath(pathSansLast);
        setActiveItem(toMenuId);
    };
    const handleOnSelect = (event, itemId) => {
        if (Object.keys(menuItems).includes(itemId)) {
            return;
        }

        onSelectLang(itemId);
        setActiveItem(itemId);
        setSelectedItem(itemId);
    };
    const getNestedItemLabel = (itemLabel) => {
        return itemLabel;
    };

    if (languages.length !== Object.keys(locales).length) {
        return null;
    }

    const menuItems = {};
    languages.forEach(lang => {
        menuItems[lang["language-id"].v] = {
            label: cockpit.format("$0 ($1)", lang["english-name"].v, lang["native-name"].v),
            subgroup: Object.fromEntries(
                locales[lang["language-id"].v].map(locale => [locale["locale-id"].v, {
                    label: locale["native-name"].v,
                }])
            ),
        };
    });

    return (
        <Menu
          id="languageMenu"
          className="language-menu"
          containsDrilldown
          drilldownItemPath={drilldownPath}
          drilledInMenus={menuDrilledIn}
          activeMenu={activeMenu}
          onSelect={handleOnSelect}
          activeItemId={activeItem}
          selected={selectedItem}
          onDrillIn={handleDrillIn}
          onDrillOut={handleDrillOut}
        >
            <MenuInput>
                <TextInput
                  aria-label="Filter menu items"
                  iconVariant="search"
                  onChange={setFilterText}
                  type="search"
                  value={filterText}
                />
            </MenuInput>
            <Divider />
            <MenuContent>
                <MenuList>
                    {Object.keys(menuItems)
                            .filter((groupKey, index) => !filterText || drilldownPath.length || menuItems[groupKey].label.toLowerCase().includes(filterText.toLowerCase()))
                            .map(groupKey => {
                                const group = menuItems[groupKey];
                                const groupLabel = group.label;

                                return (
                                    <MenuItem
                                      id={groupKey}
                                      itemId={groupKey}
                                      key={groupKey}
                                      direction="down"
                                      drilldownMenu={
                                          <DrilldownMenu id={"drilldownMenu_" + groupKey}>
                                              <MenuItem itemId={groupKey} direction="up">
                                                  {groupLabel}
                                              </MenuItem>
                                              <Divider component="li" />
                                              {Object.keys(menuItems[groupKey].subgroup)
                                                      .filter((itemKey, index) => {
                                                          return (
                                                              !filterText || !drilldownPath.length ||
                                                              getNestedItemLabel(group.subgroup[itemKey].label).toLowerCase()
                                                                      .includes(filterText.toLowerCase())
                                                          );
                                                      })
                                                      .map(itemKey => {
                                                          return (
                                                              <MenuItem id={itemKey.split(".UTF-8")[0]} itemId={itemKey} key={itemKey}>
                                                                  {getNestedItemLabel(group.subgroup[itemKey].label)}
                                                              </MenuItem>
                                                          );
                                                      })}
                                          </DrilldownMenu>
                                      }>
                                        {groupLabel}
                                    </MenuItem>
                                );
                            })}
                </MenuList>
            </MenuContent>
        </Menu>
    );
};

export const InstallationLanguage = ({ onSelectLang }) => {
    const [lang, setLang] = useState("en-us");

    const handleOnContinue = () => {
        if (!lang) {
            return;
        }

        /*
         * FIXME: Anaconda API returns en_US, de_DE etc, cockpit expects en-us, de-de etc
         * Make sure to check if this is generalized enough to keep so.
         */
        const cockpitLang = lang.split(".UTF-8")[0].replace(/_/g, "-").toLowerCase();
        const cookie = "CockpitLang=" + encodeURIComponent(cockpitLang) + "; path=/; expires=Sun, 16 Jul 3567 06:23:41 GMT";
        document.cookie = cookie;
        window.localStorage.setItem("cockpit.lang", cockpitLang);
        cockpit.location.go(["summary"]);
        window.location.reload(true);
    };

    return (
        <PageSection>
            <Form>
                <Title headingLevel="h2" size="1xl">
                    WELCOME TO FEDORA...
                </Title>
                <FormGroup label={_("What language would you like to use during the installation process?")}>
                    <LanguageSelector onSelectLang={setLang} />
                </FormGroup>
                <ActionGroup>
                    <Button id="continue-btn" variant="primary" onClick={handleOnContinue}>{_("Continue")}</Button>
                    <Button variant="link">{_("Quit")}</Button>
                </ActionGroup>
            </Form>
        </PageSection>
    );
};
