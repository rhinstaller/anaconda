import os

class BrowserSnapshot():
    SNAPSHOT_NUMBER = 0

    @classmethod
    def new(cls, browser):
        browser.snapshot(f'snapshot-{browser.label}', str(cls.SNAPSHOT_NUMBER))
        cls.SNAPSHOT_NUMBER += 1


def log_step(snapshots=False, snapshot_before=False, snapshot_after=False, docstring=False):
    """ Decorator for logging steps durring testing.

    Decorated function needs to be part of class with self.browser.

    :param snapshots: Create snapshots before and after function call, defaults to False
    :type snapshots: bool, optional
    :param snapshot_before: Create snapshots before function call, defaults to False
    :type snapshot_before: bool, optional
    :param snapshot_after: Create snapshots after function call, defaults to False
    :type snapshot_after: bool, optional
    :param docstring: Print docstring of the function, defaults to False
    :type docstring: bool, optional
    """
    def decorator(function):
        def wrapper(*args, **kwargs):
            nice_args = ', '.join(str(a) for a in args[1:])
            if kwargs:
                nice_args += ', ' + ', '.join(f'{k}: {v}' for k, v in kwargs.items())
            if nice_args:
                nice_args = ', with ' + nice_args

            print(f'[TEST STEP] {function.__name__}{nice_args}')
            if docstring:
                print(f'[DOC] {function.__doc__}')

            end2end = bool(int(os.environ.get('END2END', '0')))

            if end2end and (snapshots or snapshot_before):
                BrowserSnapshot.new(args[0].browser)

            result = function(*args, **kwargs)

            if end2end and (snapshots or snapshot_after):
                BrowserSnapshot.new(args[0].browser)

            return result
        return wrapper
    return decorator

