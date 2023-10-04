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

/* Find duplicates in an array
 * @param {Array} array
 * @returns {Array} The duplicates
 */
export const findDuplicatesInArray = (array) => {
    return array.filter((item, index) => array.indexOf(item) !== index);
};

/* Check if the given arrays are equal
 * - works only with primitive values
 * @param {Array} array1
 * @param {Array} array2
 * @returns {Boolean} True if the arrays are equal
 */
export const checkIfArraysAreEqual = (array1, array2) => {
    const array1Sorted = array1.sort();
    const array2Sorted = array2.sort();

    return (
        array1Sorted.length === array2Sorted.length &&
        array1Sorted.every((value, index) => value === array2Sorted[index])
    );
};
