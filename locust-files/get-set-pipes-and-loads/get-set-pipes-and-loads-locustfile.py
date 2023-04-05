from locust import User, HttpUser, task, events
from locust.runners import MasterRunner
import logging
import redis
import time
import random
import string
import os
import math
global myRedis
global keysAndValues
global keysOnly

def elapsed_micros(start_time):
    '''
    Returns the number of microseconds since the passed start_time
    '''
    return((time.perf_counter() - start_time) * 1000 * 1000)

def rangeToRangeBins(start, end, bins):
    '''
    Takes a starting int, an ending int, and a number of bins and returns a list of tuples that breaks the
    range into the specified number of equal sized bins

    Example: rangeToRangeBins(1,100,3) = [(1, 34), (35,67), (68,100)]
    '''

    myRanges = []
    gap = (end - start) / bins
    prevRangeEnd = start - 1
    for n in range(1, bins + 1):
        myRanges.append((prevRangeEnd+1, math.ceil(n * gap + start)))
        prevRangeEnd = math.ceil(n * gap + start)
    return myRanges

def generateKeyAndValue(minKeyInt, maxKeyInt, keyNamePrefix, keyNameLength, keyValueMinChars, keyValueMaxChars, mode='RANDOM', workerNum=None, totalWorkers=None):
    '''
    Returns a keyname and key value
    :param minKeyInt: Minimum key name index
    :param maxKeyInt: Maximum key name index
    :param keyNamePrefix: Key name prefix
    :param keyNameLength: Key name length
    :param keyValueMinChars:
    :param keyValueMaxChars:
    :param mode: Generation mode [RANDOM, SEQ_AND_HALT]
    :param workerNum: Locust worker number (required for sequential generation)
    :param totalWorkers: Locust total workers (required for sequential generation)
    :return: Tuple with key name and key value
    '''

    if mode == 'RANDOM':
        while True:
            yield(
                (''.join((keyNamePrefix, str(random.randint(minKeyInt, maxKeyInt)).zfill(keyNameLength))), \
                 ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(keyValueMinChars, keyValueMaxChars)))))
    elif mode == 'SEQ_AND_HALT':
        myRangeBins = rangeToRangeBins(minKeyInt, maxKeyInt, totalWorkers)
        for i in range (myRangeBins[workerNum-1][0], myRangeBins[workerNum-1][1]+1):
            yield( (''.join((keyNamePrefix, str(i).zfill(keyNameLength))), \
                    ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(keyValueMinChars, keyValueMaxChars)))))
        while True:
            return
    elif mode == 'SEQ_AND_LOOP':
        myRangeBins = rangeToRangeBins(minKeyInt, maxKeyInt, totalWorkers)
        while True:
            for i in range (myRangeBins[workerNum-1][0], myRangeBins[workerNum-1][1]+1):
                yield( (''.join((keyNamePrefix, str(i).zfill(keyNameLength))), \
                        ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(keyValueMinChars, keyValueMaxChars)))))

def generateKeyOnly(minKeyInt, maxKeyInt, keyNamePrefix, keyNameLength, mode='RANDOM', workerNum=None, totalWorkers=None):
    '''
    Returns a keyname
    :param minKeyInt: Minimum key name index
    :param maxKeyInt: Maximum key name index
    :param keyNamePrefix: Key name prefix
    :param keyNameLength: Key name length
    :param mode: Generation mode [RANDOM, SEQ_AND_HALT]
    :param workerNum: Locust worker number (required for sequential generation)
    :param totalWorkers: Locust total workers (required for sequential generation)
    :return: Key name and key value
    '''
    if mode == 'RANDOM':
        while True:
            yield(''.join((keyNamePrefix, str(random.randint(minKeyInt, maxKeyInt)).zfill(keyNameLength))))
    elif mode == 'SEQ_AND_HALT':
        myRangeBins = rangeToRangeBins(minKeyInt, maxKeyInt, totalWorkers)
        for i in range (myRangeBins[workerNum-1][0], myRangeBins[workerNum-1][1]+1):
            yield(''.join((keyNamePrefix, str(i).zfill(keyNameLength))))
        while True:
            return
    elif mode == 'SEQ_AND_LOOP':
        myRangeBins = rangeToRangeBins(minKeyInt, maxKeyInt, totalWorkers)
        while True:
            for i in range (myRangeBins[workerNum-1][0], myRangeBins[workerNum-1][1]+1):
                yield(''.join((keyNamePrefix, str(i).zfill(keyNameLength))))

@events.init_command_line_parser.add_listener
def parse_args(parser):
    """
    Adds customer arguments to Locust
    """
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
    parser.add_argument("--key_generation_logic", type=str, env_var="RED_LOCUST_KEY_GEN_STRATEGY", default="RANDOM", help="RANDOM|SEQ_AND_LOOP|SEEK_AND_HALT")

class DataLayer():

    def __init__(self, environment):
        self.environment = environment

    def setkey(self,localRedis):

        myException = None
        start_time = time.perf_counter()
        try:
            myData = next(keysAndValues)
            localRedis.set(myData[0], myData[1])
        except StopIteration:
            raise Exception("All keys have been generated.  If all users are in this state, you should stop the test.")
            #self.environment.runner.quit()
        except Exception as e:
            myException = e

        events.request.fire(
            request_type="redis",
            name="set",
            response_time=elapsed_micros(start_time),
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=myException)

    def getkey(self,localRedis):

        myException = None
        start_time = time.perf_counter()
        try:
            myData = next(keysOnly)
            localRedis.get(myData)
        except StopIteration:
            raise Exception("All keys have been generated.  If all users are in this state, you should stop the test.")
            # self.environment.runner.quit()
        except Exception as e:
            myException = e

        events.request.fire(
            request_type="redis",
            name="get",
            response_time=elapsed_micros(start_time),
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=myException)

    def setkey_pipeline(self,localRedis):

        stopped = False
        myException = None
        start_time = time.perf_counter()
        try:
            p = localRedis.pipeline(transaction=False)
            for i in range(25-1):
                try:
                    myData = next(keysAndValues)
                    p.set(myData[0], myData[1])
                except StopIteration:
                    stopped = True
            p.execute();
        except Exception as e:
            myException = e

        events.request.fire(
            request_type="redis",
            name="set-pipe",
            response_time=elapsed_micros(start_time),
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=myException)

        if stopped:
            raise Exception("All keys have been generated.  If all users are in this state, you should stop the test.")
            # self.environment.runner.quit()

    def getkey_pipeline(self,localRedis):

        stopped = False
        myException = None
        start_time = time.perf_counter()
        try:
            p = localRedis.pipeline(transaction=False)
            for i in range(25-1):
                try:
                    myData = next(keysOnly)
                    p.get(myData)
                except StopIteration:
                    stopped = True
            p.execute();
        except Exception as e:
            myException = e

        events.request.fire(
            request_type="redis",
            name="get-pipe",
            response_time=elapsed_micros(start_time),
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=myException)

        if stopped:
            # self.environment.runner.quit()
            raise Exception("All keys have been generated.  If all users are in this state, you should stop the test.")

class ReadWrite_4to1_Half_Pipes(User):

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

class WriteOnly_Half_Pipes(User):

    global myRedis
    global keysAndValues
    global keysOnly

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(25)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

    @task(1)
    def setkey_pipeline(self):
        self.myDataLayer.setkey_pipeline(myRedis)

class WriteOnly_No_Pipes(User):

    global myRedis
    global keysAndValues
    global keysOnly

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(1)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global myRedis
    global keysAndValues
    global keysOnly

    if isinstance(environment.runner, MasterRunner):
        logging.info("Master node test start")
    else:
        logging.info("Worker or standalone node test start")

        if (environment.parsed_options.cluster in ("Y", "y", "YES", "yes", "true", "TRUE", "True")):
            redisConnection = redis.cluster.RedisCluster
            logging.info("Creating clustered Redis connection")
        else:
            redisConnection = redis.Redis
            logging.info("creating standalone Redis connection")

        myTls = environment.parsed_options.tls in ("Y", "y", "YES", "yes", "true", "TRUE", "True" )

        myRedis = redisConnection(
            host=environment.parsed_options.redis_host,
            port=environment.parsed_options.redis_port,
            username=environment.parsed_options.username,
            password=environment.parsed_options.password,
            ssl=myTls,
            socket_timeout=environment.parsed_options.timeout,
            socket_connect_timeout=environment.parsed_options.timeout)

        keysAndValues = generateKeyAndValue(
            1,
            environment.parsed_options.number_of_keys,
            environment.parsed_options.key_name_prefix,
            environment.parsed_options.key_name_length,
            environment.parsed_options.value_min_chars,
            environment.parsed_options.value_max_chars,
            mode=environment.parsed_options.key_generation_logic,
            workerNum=int(os.environ['RED_LOCUST_WORKER_NUMBER']),
            totalWorkers=int(os.environ['RED_LOCUST_WORKERS_TOTAL']))

        keysOnly = generateKeyOnly(
            1,
            environment.parsed_options.number_of_keys,
            environment.parsed_options.key_name_prefix,
            environment.parsed_options.key_name_length,
            mode=environment.parsed_options.key_generation_logic,
            workerNum=int(os.environ['RED_LOCUST_WORKER_NUMBER']),
            totalWorkers=int(os.environ['RED_LOCUST_WORKERS_TOTAL']))
