#!/bin/bash

echo $PYTHONPATH

# The path we pass to nosetests is relative to the top-level of the anaconda source dir.
nosetests -v --exclude=logpicker -a \!acceptance,\!slow tests/*_tests
