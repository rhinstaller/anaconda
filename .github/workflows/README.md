Templated workflows
===================

Almost all workflows are now built from jinja2 templates. Make sure you are editing the `.j2`
template, not the rendered `.yml` file. To rebuild the workflow files from templates, run
`make -f Makefile.am reload-infra` at any time. The rebuild depends only on the
`.branch-variables.yml` file in the repo root.

Most of the workflows are triggered by cron or comment events, so they belong only on the default
branch which is `master`. These workflows are removed by templates on other branches. If the first
line is `{% if distro_release == "rawhide" %}` then the workflow is of such kind.

When editing a template, the following roughly describes what to expect:

- Any values available for the templates come from `.branch-variables.yml` in the repo root.

- Inline variables `{$ ... $}` are replaced by values.

- Blocks `{% ... %}` let you use conditions to select which block will be present in the output.
  If you don't put anything else on a line except for the block itself, the line will completely
  disappear from the output. Prefer that and avoid using blocks inline.

- Whitespace handling is a complicated affair. YAML wants it precise, while Jinja is messy.
  If you stick to the two methods above, everything stays mostly deterministic.

How to debug/develop GH workflows
=================================

The installer team has a lot invested into the [GitHub actions](https://docs.github.com/en/actions). It works great, however, debugging might be a bit tricky especially when you get into point of debugging a non pull_request trigger (others are taken from default GitHub branch) workflow running on our self-hosted runners. For these cases this guide should help you to set-up required environment on your fork.

With pull_request GitHub workflow trigger
-----------------------------------------

The `pull_request` trigger is the only event trigger which is taking the modified workflow from the pull request directly. That makes the debugging much easier. To find out if your workflow is using this trigger try to find this line:

```yaml
on: pull_request
```

Then, you should be fine to just create PR with changes to workflow and test on that PR. You can find out more about the events triggering workflow [here](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows).

For other triggers using a fork GitHub repository
-------------------------------------------------

However, if you have any other trigger than that you need a fork because workflow is always taken from the default branch of the repository (in case of Anaconda from master branch). To debug such a workflow follow these steps:

1. Make your changes on the workflow.
2. Push these changes to your fork master branch
    ```bash
    git push -f <fork name> HEAD:master # force push current HEAD to master branch on your fork
    ```
3. Go to your fork settings page **Actions → General** and make sure that **Allow all actions and reusable workflows** is selected.
4. Run the specific workflow by executing the event trigger.
