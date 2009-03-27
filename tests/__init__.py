import os

# this has to be imported before running anything
import anaconda_log
import upgrade


def getAvailableSuites():
    root, tests_dir = os.path.split(os.path.dirname(__file__))
    modules = []

    for root, dirs, files in os.walk(tests_dir):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                basename, extension = os.path.splitext(filename)
                modules.append(os.path.join(root, basename).replace("/", "."))

    available_suites = {}
    for module in modules:
        imported = __import__(module, globals(), locals(), [module], -1)
        try:
            suite = getattr(imported, "suite")
        except AttributeError as e:
            continue

        if callable(suite):
            available_suites[module] = suite()

    return available_suites
