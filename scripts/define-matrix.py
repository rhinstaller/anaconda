#!/usr/bin/env python3
"""
Matrix generation script for GitHub Actions workflows.

It reads supported releases from .branch-variables.yml and generates matrix data
for GitHub Actions workflows.
"""

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(description="Generate matrix data for GitHub Actions workflows.")
    parser.add_argument("target_branch", nargs='?', default=None,
                        help="Target branch to filter matrix for (optional, defaults to all branches)")
    parser.add_argument("--no-use-full-releases", dest='use_full_releases', action='store_false', default=True,
                        help="Replace current branch in 'release' with empty string for consistent check names")
    parser.add_argument("--skip-releases", default="",
                        help="Comma-separated list of releases to skip in the matrix output")

    return parser.parse_args()


def load_branch_variables() -> Dict[str, Any]:
    """Load branch variables from .branch-variables.yml"""
    branch_vars_path = Path(__file__).parent.parent / ".branch-variables.yml"

    with open(branch_vars_path, 'r') as f:
        return yaml.safe_load(f)


def create_matrix_by_branch(supported_releases: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """Create matrix data organized by branch from supported releases"""
    matrix_by_branch = {}

    for rel in supported_releases:
        branch_key = rel['target_branch']

        if branch_key not in matrix_by_branch:
            matrix_by_branch[branch_key] = []

        # Create matrix entry with all required variables
        matrix_entry = {
            'release': rel['release'],
            'target_branch': rel['target_branch'],
            'ci_tag': rel['release'],
            'distro_version': rel['release'].split('-')[-1]
        }

        matrix_by_branch[branch_key].append(matrix_entry)

    return matrix_by_branch


def filter_matrix_by_branch(matrix_by_branch: Dict[str, List[Dict[str, str]]],
                           target_branch: Optional[str]) -> List[Dict[str, str]]:
    """Filter matrix data by target branch"""
    if not target_branch:
        # Get all releases from all branches
        matrix = []
        for branch_releases in matrix_by_branch.values():
            matrix.extend(branch_releases)
        return matrix
    else:
        # Get releases for specific branch
        return matrix_by_branch.get(target_branch, [])


def process_release_names(matrix: List[Dict[str, str]], use_full_releases: bool) -> List[Dict[str, str]]:
    """Replace current branch in "release" with empty string based on use_full_releases flag
       This makes name of the check for the current branch always have the same name, so that it can
       be added to required checks on GitHub."""

    if not use_full_releases:
        # Adjust release names: empty for most, full name for non-rawhide fedora releases
        processed_matrix = []
        for entry in matrix:
            new_entry = entry.copy()
            release = entry['release']

            if release.startswith('fedora-') and release != 'fedora-rawhide':
                new_entry['release'] = release
            else:
                new_entry['release'] = ''

            processed_matrix.append(new_entry)
        return processed_matrix
    else:
        # Return matrix as-is
        return matrix


def filter_ignored_releases(matrix: List[Dict[str, str]], ignore_releases: List[str]) -> List[Dict[str, str]]:
    """Filter out releases that should be ignored"""
    if not ignore_releases:
        return matrix

    return [entry for entry in matrix if entry['release'] not in ignore_releases]


def create_github_matrix(matrix: List[Dict[str, str]]) -> Dict[str, Any]:
    """Create GitHub Actions matrix format"""
    releases = [entry['release'] for entry in matrix]

    return {
        'release': releases,
        'include': matrix
    }


def main():
    """Main function to generate matrix data"""
    # Parse command line arguments
    args = parse_args()
    target_branch = args.target_branch
    use_full_releases = args.use_full_releases
    ignore_releases = [r.strip() for r in args.skip_releases.split(',') if r.strip()]

    # Load branch variables
    branch_vars = load_branch_variables()
    supported_releases = branch_vars.get('supported_releases', [])

    # Create matrix by branch
    matrix_by_branch = create_matrix_by_branch(supported_releases)

    # Filter by target branch
    matrix = filter_matrix_by_branch(matrix_by_branch, target_branch)

    # Filter out ignored releases
    matrix = filter_ignored_releases(matrix, ignore_releases)

    # Process release names
    matrix = process_release_names(matrix, use_full_releases)

    # Create GitHub matrix format
    github_matrix = create_github_matrix(matrix)

    # Output the matrix as JSON
    print(json.dumps(github_matrix))


if __name__ == '__main__':
    main()
