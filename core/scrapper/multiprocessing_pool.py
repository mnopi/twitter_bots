import multiprocessing
import os
import time

data = (
    ['a', '2'], ['b', '4'], ['c', '6'], ['d', '8'],
    ['e', '1'], ['f', '3'], ['g', '5'], ['h', '7']
)

def mp_worker(num, lock):
    # lock.acquire()
    print " Processs %i %i\tWaiting 3 seconds" % (os.getpid(), num)
    time.sleep(3)
    print " Process %i\tDONE" % num
    # lock.release()

# def mp_handler():
#     p = multiprocessing.Pool(10)
#     p.map(mp_worker, xrange(17))

# if __name__ == '__main__':
#     mp_handler()

if __name__ == "__main__":
    # manager = multiprocessing.Manager()
    # lock = manager.Lock()
    # pool = multiprocessing.Pool(processes=10)
    # for i in xrange(15):
    #     pool.apply_async(func=mp_worker, args=(i,lock))
    # pool.close()
    # pool.join()
    #
    # print 'finalized main'


    def f(task_num, lock):
            print task_num

    manager = multiprocessing.Manager()
    lock = manager.Lock()
    pool = multiprocessing.Pool(processes=10)
    for i in xrange(15):
        pool.apply_async(func=f, args=(i,lock))
    pool.close()
    pool.join()

    print 'finalized main'