import os
import re
from collections import defaultdict

DOCS_PATH = "autoapi/pyanaconda/modules"
OUTPUT_FILE = "modules.rst"

header = """Anaconda DBUS Modules
=====================

This page contains the D-Bus API documentation, grouped by modules.

.. toctree::
   :maxdepth: 2

"""


def submodule_name_to_class_name(submodule_name: str) -> str:
    """
    Convert a submodule name (e.g. 'network') to a DBus interface class name
    (e.g. 'NetworkInterface').
    """
    parts = submodule_name.split("_")
    capitalized = [p.capitalize() for p in parts]
    return "".join(capitalized) + "Interface"


def extract_summary_from_rst(index_rst_path, class_name):
    """
    Search in the given RST file for the line: .. py:class:: <class_name>
    Then take the first suitable indented line as a docstring:
      - At least 3 spaces indentation
      - Not empty
      - Does not start with 'Bases:'
    Returns the found summary (string) or None if none found.
    """
    if not os.path.isfile(index_rst_path):
        return None

    class_directive_regex = re.compile(rf"^\.\.\s+py:class::\s+{class_name}\s*$")
    next_directive_regex = re.compile(r"^\.\.\s+py:")

    with open(index_rst_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found_class = False
    min_indent = 1

    for _, line in enumerate(lines):
        striped_line = line.rstrip("\n")

        if not found_class:
            if class_directive_regex.match(striped_line):
                found_class = True
            continue
        else:
            if next_directive_regex.match(striped_line):
                break

            match_indent = re.match(r"^(\s+)(.*)$", line)
            if not match_indent:
                break

            indent_str, text = match_indent.groups()
            indent_len = len(indent_str)
            if indent_len < min_indent:
                continue

            text = text.strip()
            if not text:
                continue
            if text.startswith("Bases:"):
                continue

            return text

    return None


def build_module_tree():
    """
    Build a nested structure of modules and their interfaces:
    {
        'submodules': {
            'boss': {
                'submodules': {...},
                'interfaces': {
                    'autoapi/pyanaconda/modules/boss/boss_interface/index': 'docstring'
                }
            }
        },
        'interfaces': {...}
    }
    """
    def create_node():
        return {
            "interfaces": {},
            "submodules": defaultdict(create_node),
        }

    tree = create_node()

    for root, _, _ in os.walk(DOCS_PATH):
        if not root.endswith("_interface"):
            continue

        rel_path = os.path.relpath(root, DOCS_PATH)
        parts = rel_path.split(os.sep)
        last_part = parts[-1]
        if not last_part.endswith("_interface"):
            continue

        submodule_name = last_part[:-10]  # remove "_interface"
        class_name = submodule_name_to_class_name(submodule_name)

        index_rst_file = os.path.join(root, "index.rst")
        if not os.path.exists(index_rst_file):
            index_rst_file = os.path.join(root, "index")
        if not os.path.exists(index_rst_file):
            continue

        docstring_summary = extract_summary_from_rst(index_rst_file, class_name)

        parent_parts = parts[:-1]
        current = tree
        for p in parent_parts:
            if p.endswith("_interface"):
                p = p[:-10]
            current = current["submodules"][p]

        interface_doc_ref = os.path.join(root, "index").replace(os.sep, "/")
        current["interfaces"][interface_doc_ref] = docstring_summary

    return tree


def write_tree(f, node, current_module=None, depth=0):
    """
    Recursively write the content of the module tree to the output file.

    - depth=0: root level. Prints any interfaces found directly under the root, if any.
    - depth=1: top-level modules. Prints the module name, and the summary for the interface
      matching the module name (e.g. 'network_interface/index').
      A toctree listing references to all interfaces (including submodules) follows.
    - depth>1: recursion stops (you can adjust if deeper levels are needed).
    """
    if current_module is None:
        current_module = []

    if depth > 1:
        return

    module_name = ".".join(current_module)

    if depth == 1:
        def collect_interfaces(n):
            interfaces = dict(n["interfaces"])
            for sub in n["submodules"].values():
                interfaces.update(collect_interfaces(sub))
            return interfaces
        aggregated_interfaces = collect_interfaces(node)
    else:
        aggregated_interfaces = node["interfaces"]

    if aggregated_interfaces:
        underline = "=" if depth == 0 else "-" if depth == 1 else "~"

        if module_name:
            f.write(f"\n{module_name}\n{underline * len(module_name)}\n")

        if depth == 1 and module_name:
            main_submodule_name = current_module[-1]
            main_interface_suffix = f"{main_submodule_name}_interface/index"
            for path, summary in aggregated_interfaces.items():
                if path.endswith(main_interface_suffix) and summary:
                    f.write(f"\n{summary}\n")
                    break

        f.write("\n.. toctree::\n   :maxdepth: 1\n\n")
        for path in sorted(aggregated_interfaces.keys()):
            f.write(f"   {path}\n")

    if depth < 1:
        for sub_name in sorted(node["submodules"]):
            write_tree(f, node["submodules"][sub_name], current_module + [sub_name], depth + 1)


if __name__ == "__main__":
    module_tree = build_module_tree()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(header)
        write_tree(file, module_tree)
