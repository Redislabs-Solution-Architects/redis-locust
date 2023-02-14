#!/usr/bin/python3
import signal
import sys
import subprocess

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


for i in machines:
    if i['master']:
        master_server = i['master_internal_ip']
        if (i['server'] == "localhost"):
            p1 = subprocess.Popen(['locust', '--master', '-f', locust_file])
        else:
            p0 = subprocess.run(['scp', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", locust_file, i['user']+"@"+i['server'] + ":" + locust_file])
            p1 = subprocess.Popen(['ssh', "-t", "-t", "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", i['user']+"@"+i['server'], "locust --master -f " + locust_file])
        processes.append(p1)
    else:
        for j in range(i['workers']):
            if (i['server'] == "localhost"):
                p2 = subprocess.Popen(['locust', '--worker', '-f', locust_file])
            else:
                p0 = subprocess.run(['scp', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", locust_file, i['user']+"@"+i['server'] + ":" + locust_file])
                p2 = subprocess.Popen(['ssh', "-o UserKnownHostsFile=/dev/null", "-o StrictHostKeychecking=no", i['user']+"@"+i['server'], "locust --worker --master-host " + master_server + " -f " + locust_file])
            processes.append(p2)

exit_codes = [p.wait() for p in processes]
