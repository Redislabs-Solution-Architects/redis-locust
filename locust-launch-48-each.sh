#!/usr/bin/python3
import signal
import sys
import subprocess
import os

processes = []

def signal_handler(sig, frame):
    print('Signal handling: terminating child processes')
    for p in processes:
      p.send_signal(sig)
    sys.exit()

signal.signal(signal.SIGINT, signal_handler)

machines = [
    {'server': "tboyd-locust-master.redisdemo.com",
     'user': 'ubuntu',
     'master': True,
     'master_internal_ip': "intr-tboyd-locust-master.redisdemo.com",
     'workers': None
    },
    {'server': "tboyd-locust-worker-001.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    },
    {'server': "tboyd-locust-worker-002.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    },
    {'server': "tboyd-locust-worker-003.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    },
    {'server': "tboyd-locust-worker-004.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    },
    {'server': "tboyd-locust-worker-005.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    },
    {'server': "tboyd-locust-worker-006.redisdemo.com",
     'user': 'ubuntu',
     'master': False,
     'workers': 48
    }
    ]

locust_file = "./locust.py"
ssh_pem_file = "./"

total_workers = 0
current_worker = 0
for i in machines:
    if not i['master']:
        total_workers = total_workers + i['workers']

my_env = os.environ
my_env["RED_LOCUST_WORKERS_TOTAL"] = str(total_workers)

for i in machines:
    if i['master']:
        master_server = i['master_internal_ip']
        if (i['server'] == "localhost"):
            p1 = subprocess.Popen(['locust', '--master', '-f', locust_file])
        else:
            p0 = subprocess.run(['scp', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", locust_file, i['user']+"@"+i['server'] + ":" + locust_file])
            p1 = subprocess.Popen(['ssh', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", i['user']+"@"+i['server'], "locust --master -f " + locust_file])
        processes.append(p1)
    else:
        for j in range(i['workers']):
            current_worker = current_worker+1
            my_env = os.environ
            my_env["RED_LOCUST_WORKER_NUMBER"] = str(current_worker)
            if (i['server'] == "localhost"):
                p2 = subprocess.Popen(['locust', '--worker', '-f', locust_file], env=my_env)
            else:
                p0 = subprocess.run(['scp', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", locust_file, i['user']+"@"+i['server'] + ":" + locust_file])
                p2 = subprocess.Popen(['ssh', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no",\
                 i['user']+"@"+i['server'], \
                "export RED_LOCUST_WORKERS_TOTAL=" + str(total_workers)+";" + \
                "export RED_LOCUST_WORKER_NUMBER=" + str(current_worker) + ";" + \
                "locust --worker --master-host " + master_server + " -f " + locust_file])
            processes.append(p2)

exit_codes = [p.wait() for p in processes]
