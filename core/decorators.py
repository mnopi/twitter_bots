from threading import Lock, currentThread
from core.managers import mutex


class mlocked(object):
    """ Class enapsulating a lock and a function
    allowing it to be used as a synchronizing
    decorator making the wrapped function
    thread-safe

    http://code.activestate.com/recipes/533135-synchronization-classes-using-decorators/
    """

    def __init__(self, *args):
        self.lock = mutex

    def __call__(self, f):
        def lockedfunc(*args, **kwargs):
            try:
                self.lock.acquire()
                # print 'Acquired lock=>',currentThread()
                try:
                    # print 'done f'
                    return f(*args, **kwargs)
                except Exception, e:
                    raise e
            finally:
                # print 'Released lock=>',currentThread()
                self.lock.release()

        return lockedfunc