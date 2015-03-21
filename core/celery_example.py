import multiprocessing
import time


def do_task(n, l, i):
    from core import tasks
    r = tasks.tarea1.delay(n)
    print '(l: %i, i: %i) finished: %s' % (l, i, r.get())


# from http://stackoverflow.com/a/26687086
def do_tasks(pool):

    for x in xrange(5):
        print 'LOOKUP', x

        for i in xrange(100):
            pool.apply_async(func=do_task, args=(2,x,i))

        print 'lookup', x, 'finished'

        time.sleep(2)


    pool.close()
    pool.join()




if __name__ == '__main__':
    pool = multiprocessing.Pool(processes=50)
    do_tasks(pool)