#!/usr/bin/python3
"""
Turn the first boot menu entry in a generated grub.cfg/isolinux.cfg into two
Web UI entries - a default local one ("inst.webui") and a remote one
("inst.webui inst.webui.remote") - mirroring what the old lorax
adjust-templates-for-webui.patch did, just applied to image-builder's
already-generated boot menu configs instead of patching lorax templates.

This can't be a plain `patch` (unified diff): lorax's patch applied to a
*static* template full of unsubstituted placeholders (@PRODUCT@, @VERSION@,
...), so the same patch worked for every build. image-builder's grub.cfg/
isolinux.cfg already has real values substituted in (product name, version,
kernel path, root args), which differ per Fedora release and per build, so
a context-diff patch would stop applying the moment any of that text changes.
"""
import re
import sys


def duplicate_entry(text, pattern, group_names, make_block):
    """Find the first match of `pattern` in `text` and replace it with two
    blocks built by make_block(groups, kernel_args) - one for the local Web
    UI entry, one for the remote one."""
    m = pattern.search(text)
    if not m:
        return None
    groups = dict(zip(group_names, m.groups()))
    local_block = make_block(groups, "inst.webui", "with Web UI")
    remote_block = make_block(groups, "inst.webui inst.webui.remote", "with Web UI (remote)")
    return text[:m.start()] + local_block + "\n" + remote_block + text[m.end():]


def patch_grub(text):
    pattern = re.compile(r"menuentry '([^']*)'([^\n{]*)\{\n((?:.*\n)*?)\}", re.M)

    def make_block(groups, kernel_args, suffix):
        title, classes, body = groups["title"], groups["classes"], groups["body"]
        body = re.sub(r"^([ \t]*linux[ \t]+.*)$", rf"\1 {kernel_args}",
                       body, count=1, flags=re.M)
        return f"menuentry '{title} {suffix}'{classes}{{\n{body}}}"

    new_text = duplicate_entry(text, pattern, ["title", "classes", "body"], make_block)
    if new_text is None:
        return None
    # the local (first) Web UI entry should be the default one
    return re.sub(r'^set default="\d+"', 'set default="0"', new_text, count=1, flags=re.M)


def patch_isolinux(text):
    pattern = re.compile(r"label (\S+)\n((?:[ \t]+\S.*\n)+)", re.M)

    def make_block(groups, kernel_args, suffix):
        label_name, body = groups["label_name"], groups["body"]
        body = re.sub(r"^[ \t]*menu default\n", "", body, flags=re.M)
        body = re.sub(r"^([ \t]*append[ \t]+.*)$", rf"\1 {kernel_args}",
                       body, count=1, flags=re.M)
        body = re.sub(r"^([ \t]*menu label .*)$", rf"\1 {suffix}",
                       body, count=1, flags=re.M)
        default = "  menu default\n" if kernel_args == "inst.webui" else ""
        return f"label {label_name}-webui{'' if kernel_args == 'inst.webui' else '-remote'}\n{default}{body}"

    return duplicate_entry(text, pattern, ["label_name", "body"], make_block)


PATCHERS = {
    "grub.cfg": patch_grub,
    "grub2-bios.cfg": patch_grub,
    "grub2-efi.cfg": patch_grub,
    "isolinux.cfg": patch_isolinux,
}


def main(path):
    for suffix, patcher in PATCHERS.items():
        if path.endswith(suffix):
            break
    else:
        print(f"WARNING: don't know how to patch {path}, leaving it alone", file=sys.stderr)
        return

    text = open(path, encoding="utf-8").read()
    new_text = patcher(text)
    if new_text is None:
        print(f"WARNING: no boot menu entry found in {path}", file=sys.stderr)
        return

    open(path, "w", encoding="utf-8").write(new_text)
    print(f"Patched {path}:")
    print(new_text)


if __name__ == "__main__":
    main(sys.argv[1])
