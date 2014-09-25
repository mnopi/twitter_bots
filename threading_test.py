import random
import time



def process(thread_num, sleep_time):
    sleep_time = 5 if thread_num == 0 else 0.5
    print 'THREAD %i non critical zone (initial)' % thread_num
    with mutex:
        print 'mutex acquired by thread %i' % thread_num
        # mutex.acquire()
        time.sleep(sleep_time)
        # time.sleep(0.5)
        print 'thread %i executed' % thread_num
        # mutex.release()
        print 'mutex released by thread %i' % thread_num

    print 'THREAD %i non critical zone (final)' % thread_num



from multiprocessing import Process, Lock
# mutex = Lock()
# for i in xrange(0, 20):
#     p = Process(target=process, args=(i, random.randint(0, 5)))
#     p.start()





from scrapper.thread_pool import ThreadPool
# from threading import Lock
mutex = Lock()

pool = ThreadPool(8)
for i in xrange(0, 20):
    pool.add_task(process, i, random.randint(0, 5))
pool.wait_completion()
