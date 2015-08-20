# Enable Python coverage for subprocesses. See:
# http://nedbatchelder.com/code/coverage/subprocess.html

try:
    import coverage
    coverage.process_startup()
except ImportError:
    pass
