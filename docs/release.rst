Building a Release
==================

When the project is ready for a new release, follow these steps to build a new
release tar.gz file and sign a new release tag in git. This requires that you
have a zanata account, and have permission to push the new .pot file to the
branch you are building. See the translations.txt file for more details.

* ``git clean -d -x -f``
* ``./autogen.sh && ./configure``
* ``make bumpver``
* ``VERSION=$(grep ^AC_INIT configure.ac | awk '{print $2}' | tr -d '[],')``
* ``git commit -am "New version - $VERSION"``
* ``make release``

Check that the commit looks correct and push the new release with:

* ``git push && git push --tags``

The anaconda-$VERSION.tar.gz file and anaconda.spec can now be used to by
fedpkg to create a new anaconda rpm.

