deploy.py
=========

this script will deploy a redis cluster with:

- redis
- redis-sentinel
- twemproxy

you can deploy/start/stop/run_rediscmd/get status/reconfig proxy ... 

config
------

::

    cluster0 = {
        'cluster_name': 'cluster0',
        'user': 'ning',
        'redis': [
            # master host:port, install path         # slave
            ('127.0.0.5:20000', '/tmp/redis-20000'), ('127.0.0.5:30000', '/tmp/redis-30000'), 
            ('127.0.0.5:20001', '/tmp/redis-20001'), ('127.0.0.5:30001', '/tmp/redis-30001'),
        ],
        'sentinel':[
            ('127.0.0.5:21001', '/tmp/sentinel-21001'),
            ('127.0.0.5:21002', '/tmp/sentinel-21002'),
            ('127.0.0.5:21003', '/tmp/sentinel-21003'),
        ],
        'nutcracker': [
            ('127.0.0.5:22000', '/tmp/nutcracker-22000'),
            ('127.0.0.5:22001', '/tmp/nutcracker-22001'),
            ('127.0.0.5:22002', '/tmp/nutcracker-22002'),
        ],
    }

this will gen ``sentinel``  config::

    sentinel monitor cluster0-20000 127.0.0.5 20000 2
    sentinel down-after-milliseconds  cluster0-20000 60000
    sentinel failover-timeout cluster0-20000 180000
    sentinel parallel-syncs cluster0-20000 1
            
    sentinel monitor cluster0-20001 127.0.0.5 20001 2
    sentinel down-after-milliseconds  cluster0-20001 60000
    sentinel failover-timeout cluster0-20001 180000
    sentinel parallel-syncs cluster0-20001 1

and ``twemproxy`` config::

    cluster0:
      listen: 127.0.0.5:22000
      hash: fnv1a_64
      distribution: modula
      preconnect: true
      auto_eject_hosts: false
      redis: true
      backlog: 512
      client_connections: 0
      server_connections: 1
      server_retry_timeout: 2000
      server_failure_limit: 2
      servers:
        - 127.0.0.5:20000:1 cluster0-20000
        - 127.0.0.5:20001:1 cluster0-20001

usage
-----

::

    $ ./bin/deploy.py -h
    usage: deploy.py [-h] [-v] [-o LOGFILE] clustername op [cmd]

    positional arguments:
      clustername           cluster target 
      op                    aof_rewrite     : None
                            deploy          : deploy the binarys and config file (redis/sentinel/nutcracker) in this cluster
                            kill            : kill all instance(redis/sentinel/nutcracker) in this cluster
                            log             : show log of all instance(redis/sentinel/nutcracker) in this cluster
                            master_memory   : show used_memory_human:1.53M
                            master_qps      : instantaneous_ops_per_sec:4
                            mastercmd cmd   : run redis command against all redis Master instance, like 'INFO, GET xxxx'
                            monitor         : monitor status of the cluster
                            printcmd        : print the start/stop cmd of instance
                            rdb             : do rdb in all redis instance
                            reconfig_proxy  : None
                            rediscmd cmd    : run redis command against all redis instance, like 'INFO, GET xxxx'
                            start           : start all instance(redis/sentinel/nutcracker) in this cluster
                            status          : get status of all instance(redis/sentinel/nutcracker) in this cluster
                            stop            : stop all instance(redis/sentinel/nutcracker) in this cluster
      cmd                   the redis/ssh cmd like "INFO"

start cluster::

    $ ./bin/deploy.py cluster0 deploy
    $ ./bin/deploy.py cluster0 start
    2013-12-18 14:34:15,934 [MainThread] [INFO] start running: ./bin/deploy.py -v start cluster0
    2013-12-18 14:34:15,934 [MainThread] [INFO] Namespace(logfile='log/deploy.log', op='start', target='cluster0', verbose=1)
    2013-12-18 14:34:15,936 [MainThread] [NOTICE] start redis
    2013-12-18 14:34:15,936 [MainThread] [INFO] start [RedisServer:127.0.0.5:20000]
    2013-12-18 14:34:16,122 [MainThread] [INFO] start [RedisServer:127.0.0.5:30000]
    2013-12-18 14:34:16,301 [MainThread] [INFO] start [RedisServer:127.0.0.5:20001]
    2013-12-18 14:34:16,489 [MainThread] [INFO] start [RedisServer:127.0.0.5:30001]
    2013-12-18 14:34:16,691 [MainThread] [INFO] start [RedisServer:127.0.0.5:20002]
    2013-12-18 14:34:16,905 [MainThread] [INFO] start [RedisServer:127.0.0.5:30002]
    2013-12-18 14:34:17,102 [MainThread] [INFO] start [RedisServer:127.0.0.5:20003]
    2013-12-18 14:34:17,310 [MainThread] [INFO] start [RedisServer:127.0.0.5:30003]

    2013-12-18 14:34:17,513 [MainThread] [NOTICE] start sentinel
    2013-12-18 14:34:17,513 [MainThread] [INFO] start [Sentinel:127.0.0.5:21001]
    2013-12-18 14:34:17,706 [MainThread] [INFO] start [Sentinel:127.0.0.5:21002]
    2013-12-18 14:34:17,913 [MainThread] [INFO] start [Sentinel:127.0.0.5:21003]

    2013-12-18 14:34:18,102 [MainThread] [NOTICE] start nutcracker
    2013-12-18 14:34:18,102 [MainThread] [INFO] start [NutCracker:127.0.0.5:22000]
    2013-12-18 14:34:18,325 [MainThread] [INFO] start [NutCracker:127.0.0.5:22001]
    2013-12-18 14:34:18,516 [MainThread] [INFO] start [NutCracker:127.0.0.5:22002]

run cmd on each master::

    $ ./bin/deploy.py cluster0 mastercmd 'get "hello"'
    2013-12-24 13:51:39,748 [MainThread] [INFO] [RedisServer:127.0.0.5:20000]: get "hello"
    [RedisServer:127.0.0.5:20000] xxxxx
    2013-12-24 13:51:39,752 [MainThread] [INFO] [RedisServer:127.0.0.5:20001]: get "hello"
    [RedisServer:127.0.0.5:20001] 
    2013-12-24 13:51:39,756 [MainThread] [INFO] [RedisServer:127.0.0.5:20002]: get "hello"
    [RedisServer:127.0.0.5:20002] 
    2013-12-24 13:51:39,760 [MainThread] [INFO] [RedisServer:127.0.0.5:20003]: get "hello"
    [RedisServer:127.0.0.5:20003] world

dump rdb::

    $ ./bin/deploy.py cluster0 rdb

monitor qps/memory::

    $ ./bin/deploy.py cluster0 mq
    2013-12-24 14:21:05,841 [MainThread] [INFO] start running: ./bin/deploy.py -v cluster0 mq
    2013-12-24 14:21:05,842 [MainThread] [INFO] Namespace(cmd=None, logfile='log/deploy.log', op='mq', target='cluster0', verbose=1)
    20000 20001 20002 20003
        6     5     5     6
        6     6     5     6
        6     6     5     6
     4741     6     6     6
    33106     5     5     6
    46639     8     7     7
    42265     6     5     7

gen_conf.py
===========

use the config::

    BASEDIR = '/tmp/r'
    HOSTS = [
            '127.0.1.1',
            '127.0.1.2',
            '127.0.1.3',
            '127.0.1.4',
            ]
    MASTER_PER_MACHINE = 2
    SLAVE_PORT_INCREASE = 10000

it will gen the deploy.py config like this:

.. image:: doc/twemproxy-sentinel-cluster.png

Dependency
==========

- pcl: https://github.com/idning/pcl
