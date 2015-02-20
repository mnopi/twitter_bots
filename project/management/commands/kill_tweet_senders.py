import psutil

__author__ = 'robots'


for proc in psutil.process_iter():
    cwd = proc.getcwd()
    for c in cwd:
        if 'phantomjs_prod_linux_bin' in c or 'tweet_sender' in c:
            proc.kill()
            break