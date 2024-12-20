Templated workflows
-------------------

Almost all workflows are now built from jinja2 templates. Make sure you are editing the `.j2`
template, not the rendered `.yml` file. To rebuild the workflow files from templates, run
`make -f Makefile.am reload-infra` at any time. The rebuild depends only on the
`.branch-variables.yml` file in the repo root.

Most of the workflows are triggered by cron or comment events, so they belong only on the default
branch which is `main`. These workflows are removed by templates on other branches. If the first
line is `{% if distro_release == "rawhide" %}` then the workflow is of such kind.

When editing a template, the following roughly describes what to expect:

- Any values available for the templates come from `.branch-variables.yml` in the repo root.

- Inline variables `{$ ... $}` are replaced by values.

- Blocks `{% ... %}` let you use conditions to select which block will be present in the output.
  If you don't put anything else on a line except for the block itself, the line will completely
  disappear from the output. Prefer that and avoid using blocks inline.

- Whitespace handling is a complicated affair. YAML wants it precise, while Jinja is messy.
  If you stick to the two methods above, everything stays mostly deterministic.
