# function 'compute' is distributed and executed with arguments
# supplied with 'cluster.submit' below
import socket
from core.scrapper.thread_pool import ThreadPool
import dispy, random

host = socket.gethostname()

if host == 'p1':
    # corriendo en ofi
    CLIENT_IP_PRIVATE = '192.168.1.115'
    CLIENT_IP_PUBLIC = '88.26.212.82'
    DISPY_NODES = [
        CLIENT_IP_PRIVATE,  # local
        '77.228.76.30',  # casa
        # '*',
    ]
else:
    # corriendo en casa
    CLIENT_IP_PRIVATE = '192.168.0.115'
    CLIENT_IP_PUBLIC = '77.228.76.30'
    DISPY_NODES = [
        CLIENT_IP_PRIVATE,  # local
        '88.26.212.82',  # pepino1
        # '*',
    ]

DISPY_NODES += [
    '46.101.61.145',  # gallina1
]


def compute(n, b='casa'):
    import time, socket
    # time.sleep(n)
    host = socket.gethostname()
    # return (host, n)
    time.sleep(5)
    return host, n*100, b


cluster = dispy.JobCluster(compute, ip_addr=CLIENT_IP_PRIVATE, ext_ip_addr=CLIENT_IP_PUBLIC, nodes=DISPY_NODES)


def do_task():
    job = cluster.submit(random.randint(5, 20), b='mierda')
    host, n, b = job()
    # print('%s executed job %s at %s with %s' % (host, job.id, job.start_time, n))
    print 'node %s says: %i %s' % (host, n, b)


if __name__ == '__main__':

    # nodes = [
    #     ('46.101.61.145', 51348),
    #     # ('127.0.0.1', 51348),
    # ]

    try:
        jobs = []
        for n in range(100):
            job = cluster.submit(random.randint(5,20), b='mierda')
            job.id = n
            jobs.append(job)
        # cluster.wait() # wait until all jobs finish
        for job in jobs:
            # host, n = job() # waits for job to finish and returns results
            h, n, b = job() # waits for job to finish and returns results
            # print('%s executed job %s at %s with %s' % (host, job.id, job.start_time, n))
            print 'node %s says: %i %s' % (h, n, b)
            # other fields of 'job' that may be useful:
            # job.stdout, job.stderr, job.exception, job.ip_addr, job.end_time
        cluster.stats()
    except KeyboardInterrupt:
        print 'olaaa'

    # pool = ThreadPool(50)
    # for i in xrange(0, 50):
    #     pool.add_task(do_task)
    # pool.wait_completion()