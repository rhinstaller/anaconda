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

import React, { useState } from 'react';
import cockpit from 'cockpit';

import {
    ActionGroup,
    Button,
    Form, FormGroup,
    Menu, MenuContent, MenuList, MenuInput, MenuItem, Divider, DrilldownMenu,
    PageSection,
    TextInput, Title,
} from '@patternfly/react-core';

import './InstallationLanguage.scss';

const _ = cockpit.gettext;

// Use this untill we can use the API to get the language listings
const menuItems = {
    english: {
        label: 'English',
        subgroup: {
            enUS: {
                label: 'United States'
            },
            enUK: {
                label: 'United Kingdom'
            }
        }
    },
    de: {
        label: 'Deutsch',
        subgroup: {
            deDE: {
                label: 'Deutschland'
            },
            deLU: {
                label: 'Luxemburg'
            }
        }
    }
};

const LanguageSelector = ({ defaultLang, onSelectLang }) => {
    const [activeItem, setActiveItem] = useState(defaultLang);
    const [activeMenu, setActiveMenu] = useState('languageMenu');
    const [drilldownPath, setDrilldownPath] = useState([]);
    const [filterText, setFilterText] = useState('');
    const [menuDrilledIn, setMenuDrilledIn] = useState([]);
    const [menuHeights, setMenuHeights] = useState([]);
    const [selectedItem, setSelectedItem] = useState(defaultLang);

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
    const handleSetHeight = (menuId, height) => {
        if (!menuHeights[menuId]) {
            setMenuHeights({
                ...menuHeights,
                [menuId]: height
            });
        }
    };
    const handleOnSelect = (event, itemId) => {
        if (Object.keys(menuItems).includes(itemId)) {
            return;
        }

        onSelectLang(itemId);
        setActiveItem(itemId);
        setSelectedItem(itemId);
    };
    const getNestedItemLabel = (groupLabel, itemLabel) => {
        return groupLabel + ' (' + itemLabel + ')';
    };

    return (
        <Menu
          id='languageMenu'
          className='language-menu'
          containsDrilldown
          drilldownItemPath={drilldownPath}
          drilledInMenus={menuDrilledIn}
          activeMenu={activeMenu}
          onSelect={handleOnSelect}
          activeItemId={activeItem}
          selected={selectedItem}
          onDrillIn={handleDrillIn}
          onDrillOut={handleDrillOut}
          onGetMenuHeight={handleSetHeight}
        >
            <MenuInput>
                <TextInput
                  aria-label='Filter menu items'
                  iconVariant='search'
                  onChange={setFilterText}
                  type='search'
                  value={filterText}
                />
            </MenuInput>
            <Divider />
            <MenuContent menuHeight={`${menuHeights[activeMenu]}px`}>
                <MenuList>
                    {Object.keys(menuItems)
                            .filter(groupKey => !filterText || drilldownPath.length || menuItems[groupKey].label.toLowerCase().includes(filterText.toLowerCase()))
                            .map(groupKey => {
                                const group = menuItems[groupKey];
                                const groupLabel = group.label;

                                return (
                                    <MenuItem
                                      itemId={groupKey}
                                      key={groupKey}
                                      direction='down'
                                      drilldownMenu={
                                          <DrilldownMenu id={'drilldownMenu_' + groupKey}>
                                              <MenuItem itemId={groupKey} direction='up'>
                                                  {groupLabel}
                                              </MenuItem>
                                              <Divider component='li' />
                                              {Object.keys(menuItems[groupKey].subgroup)
                                                      .filter(itemKey => {
                                                          return (
                                                              !filterText || !drilldownPath.length ||
                                                              getNestedItemLabel(groupLabel, group.subgroup[itemKey].label).toLowerCase()
                                                                      .includes(filterText.toLowerCase())
                                                          );
                                                      })
                                                      .map(itemKey => {
                                                          return (
                                                              <MenuItem itemId={itemKey} key={itemKey}>
                                                                  {getNestedItemLabel(groupLabel, group.subgroup[itemKey].label)}
                                                              </MenuItem>
                                                          );
                                                      })}
                                          </DrilldownMenu>
                                      }
                                    >
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
    const [lang, setLang] = useState('enUS');

    const handleOnContinue = () => onSelectLang(lang);

    return (
        <PageSection>
            <Form>
                <Title headingLevel='h2' size='1xl'>
                    WELCOME TO FEDORA...
                </Title>
                <FormGroup label={_("What language would you like to use during the installation process?")}>
                    <LanguageSelector defaultLang='enUS' onSelectLang={setLang} />
                </FormGroup>
                <ActionGroup>
                    <Button id='continue-btn' variant='primary' onClick={handleOnContinue}>{_("Continue")}</Button>
                    <Button variant='link'>{_("Quit")}</Button>
                </ActionGroup>
            </Form>
        </PageSection>
    );
};
