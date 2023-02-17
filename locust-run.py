from locust import User, HttpUser, task, events
from locust.runners import MasterRunner
import logging
import redis
import time
import random
import string
from pprint import pformat
import os

global myRedis
global keysAndValues
global keysOnly

def record_request_meta(request_type, name, start_time, end_time, response_length, response, exception):
    """
    Function to record locust request, based on standard locust request meta data
    repsonse time is calculated form inputs and is expressed in microseconds
    """
    request_meta = {
        "request_type": request_type,
        "name": name,
        "start_time": start_time,
        "response_time": (time.perf_counter() - start_time) * 1000 * 1000,
        "response_length": response_length,
        "response": response,
        "context": {},
        "exception": exception }

    if exception:
        events.request_failure.fire(**request_meta)
    else:
        events.request_success.fire(**request_meta)

def rangeToRangeBuckets(minValue, maxValue, buckets):
    step = (maxValue - minValue)  / buckets
    return [((round((step*i)+minValue), round(step*(i+1)+minValue))) for i in range(buckets)]

def generateKeyAndValue(minKeyInt, maxKeyInt, keyNamePrefix, keyNameLength, keyValueMinChars, keyValueMaxChars, mode='RANDOM', workerNum=None, totalWorkers=None):
    if mode == 'RANDOM':
        while True:
            yield(
                (''.join((keyNamePrefix, str(random.randint(minKeyInt, maxKeyInt)).zfill(keyNameLength))), \
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(keyValueMinChars, keyValueMaxChars)))))
    elif mode == 'SEQ_PER_WORKER_AND_EXIT':
        myRangeBuckets = rangeToRangeBuckets(minKeyInt, maxKeyInt, totalWorkers)
        for i in range (myRangeBuckets[workerNum-1][0], myRangeBuckets[workerNum-1][1]+1):
            yield( (''.join((keyNamePrefix, str(i).zfill(keyNameLength))), \
             ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(keyValueMinChars, keyValueMaxChars)))))
        while True:
            return

def generateKeyOnly(minKeyInt, maxKeyInt, keyNamePrefix, keyNameLength, mode='RANDOM', workerNum=None, totalWorkers=None):
    if mode == 'RANDOM':
        while True:
            yield(''.join((keyNamePrefix, str(random.randint(minKeyInt, maxKeyInt)).zfill(keyNameLength))))
    elif mode == 'SEQ_PER_WORKER_AND_EXIT':
        myRangeBuckets = rangeToRangeBuckets(minKeyInt, maxKeyInt, totalWorkers)
        for i in range (myRangeBuckets[workerNum-1][0], myRangeBuckets[workerNum-1][1]+1):
            yield(''.join((keyNamePrefix, str(i).zfill(keyNameLength))))
        while True:
            return


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--redis_host", type=str, env_var="RED_LOCUST_HOST", default="localhost", help="Host for Redis")
    parser.add_argument("--redis_port", type=int, env_var="RED_LOCUST_PORT", default=6379, help="Port for Redis")
    parser.add_argument("--username", type=str, env_var="RED_LOCUST_USERNAME", default="", help="Username for Redis")
    parser.add_argument("--password", type=str, env_var="RED_LOCUST_PASSWORD", default="", help="Password for Redis")
    parser.add_argument("--timeout", type=int, env_var="RED_LOCUST_TIMEOUT", default=500, help="Timeout for Redis in ms")
    parser.add_argument("--cluster", type=str, env_var="RED_LOCUST_CLUSTER", default="N", help="Cluster mode (Y/N)")
    parser.add_argument("--tls", type=str, env_var="RED_LOCUST_TLS", default="N", help="TLS (Y/N)")
    parser.add_argument("--key_name_prefix", type=str, env_var="RED_LOCUST_KEY_NAME_PREFIX", default="rloc:", help="Prefix for key names")
    parser.add_argument("--key_name_length", type=int, env_var="RED_LOCUST_KEY_NAME_LENGTH", default=10, help="Length (ie digits) of key name (not including prefix)")
    parser.add_argument("--number_of_keys", type=int, env_var="RED_LOCUST_NUM_OF_KEYS", default=1000000, help="Number of keys")
    parser.add_argument("--value_min_chars", type=int, env_var="RED_LOCUST_VALUE_MIN_BYTES", default=8, help="Minimum characters to store in key value")
    parser.add_argument("--value_max_chars", type=int, env_var="RED_LOCUST_VALUE_MAX_BYTES", default=8, help="Maximum characters to store in key value")
    parser.add_argument("--version_display", type=str, env_var="RED_VERSION_DISPLAY", default="0.2", help="Just used to show locust file version in UI")

@events.test_start.add_listener
def _(environment, **kw):
    print(f"Custom argument supplied: {environment.parsed_options.redis_host}")
    print(f"Custom argument supplied: {environment.parsed_options.redis_port}")
    print(f"Custom argument supplied: {environment.parsed_options.username}")
    print(f"Custom argument supplied: {environment.parsed_options.timeout}")
    print(f"Custom argument supplied: {environment.parsed_options.cluster}")

class DataLayer():

    def __init__(self, environment):
        self.environment = environment

    def setkey(self,localRedis):

        myException = None
        myResponse = None
        trans_start_time = time.perf_counter()
        try:
            myData = next(keysAndValues)
            myResponse = localRedis.set(myData[0], myData[1])
        except StopIteration:
            self.environment.runner.quit()
        except Exception as e:
            myException = e

        record_request_meta(
            request_type = "single",
            name = "set",
            start_time = trans_start_time,
            end_time = time.perf_counter(),
            response_length = 0,
            response = myResponse,
            exception = myException)

    def getkey(self,localRedis):

        myException = None
        myResponse = None
        trans_start_time = time.perf_counter()
        try:
            myData = next(keysOnly)
            myResponse = localRedis.get(myData)
        except StopIteration:
            self.environment.runner.quit()
        except Exception as e:
            myException = e

        record_request_meta(
            request_type = "single",
            name = "get",
            start_time = trans_start_time,
            end_time = time.perf_counter(),
            response_length = 0,
            response = myResponse,
            exception = myException)

    def setkey_pipeline(self,localRedis):

        stopped = False
        myException = None
        myResponse = None
        trans_start_time = time.perf_counter()
        try:
            p = localRedis.pipeline(transaction=False)
            start_perf_counter = time.perf_counter()
            for i in range(25-1):
                try:
                    myData = next(keysAndValues)
                    r = p.set(myData[0], myData[1])
                except StopIteration:
                    stopped = True
            myResponse = p.execute();
        except Exception as e:
            myException = e

        record_request_meta(
            request_type = "pipe25",
            name = "set-pipe",
            start_time = trans_start_time,
            end_time = time.perf_counter(),
            response_length = 0,
            response = myResponse,
            exception = myException)

        if stopped:
            self.environment.runner.quit()

    def getkey_pipeline(self,localRedis):

        stopped = False
        myException = None
        myResponse = None
        trans_start_time = time.perf_counter()
        try:
            p = localRedis.pipeline(transaction=False)
            for i in range(25-1):
                try:
                    myData = next(keysOnly)
                    r = p.get(myData)
                except StopIteration:
                    stopped = True
            myResponse = p.execute();
        except Exception as e:
            myException = e

        record_request_meta(
            request_type = "pipe25",
            name = "get-pipe",
            start_time = trans_start_time,
            end_time = time.perf_counter(),
            response_length = 0,
            response = myResponse,
            exception = myException)

        if stopped:
            self.environment.runner.quit()

class RedisUser(User):

    global myRedis
    global keysAndValues
    global keysOnly

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(100)
    def getkey(self):
        self.myDataLayer.getkey(myRedis)

    @task(25)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

    @task(4)
    def getkey_pipeline(self):
        self.myDataLayer.getkey_pipeline(myRedis)

    @task(1)
    def setkey_pipeline(self):
        self.myDataLayer.setkey_pipeline(myRedis)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global myRedis
    global keysAndValues
    global keysOnly

    if isinstance(environment.runner, MasterRunner):
        logging.info("Master node test start")
    else:
        logging.info("RED_LOCUST_WORKERS_TOTAL: " + os.environ['RED_LOCUST_WORKERS_TOTAL'])
        logging.info("RED_LOCUST_WORKER_NUMBER: " + os.environ['RED_LOCUST_WORKER_NUMBER'])
        logging.info("environment:" + pformat(environment.__dir__()))
        logging.info("environment.parsed_options: " + pformat(environment.parsed_options))
        logging.info("environment.runner:" + pformat(environment.runner.__dir__()))
        logging.info("Worker or standalone node test start")
        if (environment.parsed_options.cluster == "Y"):
            logging.info("Creating clustered Redis connection")
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            myRedis = redis.cluster.RedisCluster( \
                host=environment.parsed_options.redis_host, \
                port=environment.parsed_options.redis_port, \
                username=environment.parsed_options.username, \
                password=environment.parsed_options.password, \
                ssl=myTls, \
                socket_timeout=environment.parsed_options.timeout, \
                socket_connect_timeout=environment.parsed_options.timeout)
        else:
            logging.info("creating standalone Redis connection")
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            myRedis = redis.Redis( \
                host=environment.parsed_options.redis_host, \
                port=environment.parsed_options.redis_port, \
                username=environment.parsed_options.username, \
                password=environment.parsed_options.password, \
                ssl=myTls, \
                socket_timeout=environment.parsed_options.timeout, \
                socket_connect_timeout=environment.parsed_options.timeout)
        # Create data generators
        keysAndValues = generateKeyAndValue(
            1,
            environment.parsed_options.number_of_keys,
            environment.parsed_options.key_name_prefix,
            environment.parsed_options.key_name_length,
            environment.parsed_options.value_min_chars,
            environment.parsed_options.value_max_chars,
            mode='RANDOM',
            workerNum=int(os.environ['RED_LOCUST_WORKER_NUMBER']),
            totalWorkers=int(os.environ['RED_LOCUST_WORKERS_TOTAL']))
        keysOnly = generateKeyOnly(
            1,
            environment.parsed_options.number_of_keys,
            environment.parsed_options.key_name_prefix,
            environment.parsed_options.key_name_length,
            mode='RANDOM',
            workerNum=int(os.environ['RED_LOCUST_WORKER_NUMBER']),
            totalWorkers=int(os.environ['RED_LOCUST_WORKERS_TOTAL']))
