import random
import time


from threading import Lock, currentThread

mutex = Lock()

class synchronized(object):
    """ Class enapsulating a lock and a function
    allowing it to be used as a synchronizing
    decorator making the wrapped function
    thread-safe """

    def __init__(self, *args):
        self.lock = Lock()

    def __call__(self, f):
        def lockedfunc(*args, **kwargs):
            try:
                self.lock.acquire()
                print 'Acquired lock=>',currentThread()
                try:
                    print 'done f'
                    return f(*args, **kwargs)
                except Exception, e:
                    raise
            finally:
                print 'Released lock=>',currentThread()
                self.lock.release()

        return lockedfunc


def mlock(orig_f):
    def inner(*args, **kwargs):
        try:
            mutex.acquire()
            print 'Acquired lock=>',currentThread()
            print 'done f'
            return orig_f(*args, **kwargs)
        finally:
            print 'Released lock=>',currentThread()
            mutex.release()

    return inner



@synchronized()
def f1(sleep_time):
    time.sleep(sleep_time)
    return 'thread %s executed' % currentThread()

def process(sleep_time):
    # sleep_time = 5 if thread_num == 0 else 0.5
    f1(sleep_time)
    print 'mierda %s' % currentThread()

from core.scrapper.thread_pool import ThreadPool
# from threading import Lock

pool = ThreadPool(2)
for i in xrange(0, 5):
    pool.add_task(process, random.randint(0, 5))
pool.wait_completion()





