#!/usr/bin/python
#-*- coding:utf-8 -*-

import sys

REQUIRED_PATHS = ["/usr/lib/anaconda",
                  "/usr/share/system-config-date"]
sys.path.extend(REQUIRED_PATHS)

import unittest
import tests
import string
from optparse import OptionParser


def getFullTestName(test, full_test_names):
    tests = []
    for full_test_name in full_test_names:
        if full_test_name.lower().find(test) != -1:
            tests.append(full_test_name)

    return tests


if __name__ == "__main__":
    usage = "usage: %prog [options] [test1 test2 ...]"
    parser = OptionParser(usage)
    parser.add_option("-l", "--list", action="store_true", default=False,
                      help="print all available tests and exit")

    (options, args) = parser.parse_args(sys.argv[1:])

    print "Searching for test suites"
    available_suites = tests.getAvailableSuites()
    test_keys = available_suites.keys()
    if not test_keys:
        print "No test suites available, exiting"
        sys.exit(1)

    test_keys.sort()

    if options.list:
        print "\nAvailable tests:"
        for test_name in test_keys:
            print test_name
        sys.exit(0)

    tests_to_run = []

    if len(args) == 0:
        # interactive mode
        print "Running in interactive mode"
        print "\nAvailable tests:"
        test_num = 0
        for test_name in test_keys:
            print "[%3d] %s" % (test_num, test_name)
            test_num += 1
        print

        try:
            input_string = raw_input("Type in the test you want to run, "
                                     "or \"all\" to run all listed tests: ")
        except KeyboardInterrupt as e:
            print "\nAborted by user"
            sys.exit(1)

        for arg in input_string.split():
            if arg.isdigit():
                arg = int(arg)
                try:
                    args.append(test_keys[arg])
                except KeyError as e:
                    pass
            else:
                args.append(arg)

    args = map(string.lower, args)
    if "all" in args:
        tests_to_run = test_keys[:]
    else:
        for arg in args:
            matching_tests = getFullTestName(arg, test_keys)
            tests_to_run.extend(filter(lambda test: test not in tests_to_run,
                                       matching_tests))

    # run the tests
    if tests_to_run:
        tests_to_run.sort()
        print "Running tests: %s" % tests_to_run
        test_suite = unittest.TestSuite([available_suites[test]
                                         for test in tests_to_run])

        try:
            result = unittest.TextTestRunner(verbosity=2).run(test_suite)
        except KeyboardInterrupt as e:
            print "\nAborted by user"
            sys.exit(1)

        if result.wasSuccessful():
            print "\nAll tests OK"
            sys.exit(0)
        else:
            print "\nTests finished with %d errors and %d failures" % (len(result.errors),
                                                                       len(result.failures))
            sys.exit(2)
    else:
        print "No test suites matching your criteria found, exiting"
        sys.exit(1)
