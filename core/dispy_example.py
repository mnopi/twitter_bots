# function 'compute' is distributed and executed with arguments
# supplied with 'cluster.submit' below
from core.scrapper.thread_pool import ThreadPool
import dispy, random


CLIENT_IP_PRIVATE = '192.168.1.115'
CLIENT_IP_PUBLIC = '88.26.212.82'
# CLIENT_IP_PRIVATE = '192.168.0.115'
# CLIENT_IP_PUBLIC = '77.228.76.30'

NODES = [
    # '46.101.61.145',  # gallina1
    # '88.26.212.82',  # pepino1
    CLIENT_IP_PRIVATE,
    # '*',
]


def compute(n, b='casa'):
    import time, socket
    # time.sleep(n)
    host = socket.gethostname()
    # return (host, n)
    time.sleep(5)
    return host, n*100, b


cluster = dispy.JobCluster(compute, ip_addr=CLIENT_IP_PRIVATE, ext_ip_addr=CLIENT_IP_PUBLIC, nodes=NODES)


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

    jobs = []
    for n in range(300):
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


    # pool = ThreadPool(50)
    # for i in xrange(0, 50):
    #     pool.add_task(do_task)
    # pool.wait_completion()