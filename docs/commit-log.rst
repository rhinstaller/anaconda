Rules for commit messages
==========================

git commit messages for anaconda should follow a consistent format.  The
following are rules to follow when committing a change to the git repo:

1) The first line of the commit message should be a short summary of the
   change in the patch.  The summary lines need to be short.
   Ideally less than 75 characters, but certainly not longer than 80.

   Here is acceptable first line for git commit message::

       Introduce a new screen for setting your preferred email client

2) The main body of the commit message should begin TWO LINES below the
   summary line you just entered (that is, there needs to be a blank line
   between the one line summary and the start of the long commit message).
   Please document the change and explain the patch here.  Use multiple
   paragraphs and keep the lines < 75 chars.  DO NOT indent these lines.
   Everything in the git commit message should be left justified.  PLEASE
   wrap long lines.  If you don't, the 'git log' output ends up looking
   stupid on 80 column terminals.

3) For RHEL or CentOS Stream bugs, all commits need to reference a bug
   issue name. These bugs can be filed
   `here <https://issues.redhat.com/projects/RHEL/issues>`_.

   If you have a patch that is Related to or Reverts another bug,
   you may add those line to the end of the long commit message in this
   format::

       Related: RHEL-ISSUENUMBER
       Reverts: RHEL-ISSUENUMBER
       Resolves: RHEL-ISSUENUMBER

   These entries should come at the end of the long commit message and
   must follow the format above.  You may have as many of these lines as
   appropriate for the patch.

   On RHEL branches, the 'bumpver' process will verify that each patch for
   the release references a RHEL issue.  The scripts/makebumpver script
   will extract the bug issues from RHEL branch commits and do two things.
   First, it verifies that the bug referenced is a RHEL bug and in correct
   states.  Second, it adds the appropriate Resolves/Related/Reverts line
   to the RPM spec file changelog.

It is recommended to use the pre-push hook checking commit messages for RHEL bug
numbers and checking the referenced bugs for all the necessary acks. To make it
work, just copy the scripts/githooks/pre-push and
scripts/githooks/check_commit_msg.sh scripts to the .git/hooks/ directory.
