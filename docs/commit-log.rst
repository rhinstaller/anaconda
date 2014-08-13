Rules for commit messages
==========================

git commit messages for anaconda should follow a consistent format.  The
following are rules to follow when committing a change to the git repo:

1) The first line of the commit message should be a short summary of the
   change in the patch.  We also place (#BUGNUMBER) at the end of this
   line to indicate the bugzilla.redhat.com bug number addressed in this
   patch.  The bug number is optional since there may be no bug number,
   but if you have one you are addressing, please include it on the
   summary line.  Lastly, the summary lines need to be short.  Ideally
   less than 75 characters, but certainly not longer than 80.

   Here are acceptable first lines for git commit messages:

       Check partition and filesystem type on upgrade (#123456)
       Fix bootloader configuration setup on ppc64 (#987654)
       Introduce a new screen for setting your preferred email client

   The last one would be a new feature that we didn't have a bug number
   for.

2) The main body of the commit message should begin TWO LINES below the
   summary line you just entered (that is, there needs to be a blank line
   between the one line summary and the start of the long commit message).
   Please document the change and explain the patch here.  Use multiple
   paragraphs and keep the lines < 75 chars.  DO NOT indent these lines.
   Everything in the git commit message should be left justified.  PLEASE
   wrap long lines.  If you don't, the 'git log' output ends up looking
   stupid on 80 column terminals.

3) For RHEL bugs, all commits need to reference a bug number.  You may
   follow one of two formats for specifying the bug number in a RHEL commit.

   a)  Put the bug number on the summary line in (#BUGNUMBER) format.  Bugs
       listed this way are treated as 'Resolves' patches in the RHEL
       universe.

   b)  If you have a patch that is Related to or Conflicts with another bug,
       you may add those lines to the end of the long commit message in this
       format::

           Related: rhbz#BUGNUMBER
           Conflicts: rhbz#BUGNUMBER
           Resolves: rhbz#BUGNUMBER

       These entries should come at the end of the long commit message and
       must follow the format above.  You may have as many of these lines as
       appropriate for the patch.

   c)  Patches that are 'Resolves' patches have two methods to specify the
       bug numbers, but Related and Conflicts can only be listed in the long
       commit message.

   On RHEL branches, the 'bumpver' process will verify that each patch for
   the release references a RHEL bug number.  The scripts/makebumpver script
   will extract the bug numbers from RHEL branch commits and do two things.
   First, it verifies that the bug referenced is a RHEL bug and in correct
   states.  Second, it adds the appropriate Resolves/Related/Conflicts line
   to the RPM spec file changelog.

It is recommended to use the pre-push hook checking commit messages for RHEL bug
numbers and checking the referenced bugs for all the necessary acks. To make it
work, just copy the scripts/githooks/pre-push and
scripts/githooks/check_commit_msg.sh scripts to the .git/hooks/ directory.
