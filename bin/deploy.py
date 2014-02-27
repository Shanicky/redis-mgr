#!/usr/bin/env python
#coding: utf-8

import os
import sys
from pprint import pprint

PWD = os.path.dirname(os.path.realpath(__file__))
WORKDIR = os.path.join(PWD,  '../')
sys.path.append(os.path.join(WORKDIR, 'lib/'))
sys.path.append(os.path.join(WORKDIR, 'conf/'))

from server_modules import *
from utils import *
from monitor import Monitor, Benchmark
from migrate import Migrate
from webserver import WebServer

class Cluster(object, Monitor, Benchmark, WebServer, Migrate):
    def __init__(self, args):
        self.args = args
        self._rewrite_redis_config()

        self.all_redis = [ self._make_redis(s) for s in self.args['redis'] ]
        masters = self.all_redis[::2]

        self.all_sentinel = [Sentinel(self.args['user'], hp, path, masters) for hp, path in self.args['sentinel'] ]
        self.all_nutcracker = [NutCracker(self.args['user'], hp, path, masters) for hp, path in self.args['nutcracker'] ]
        for m in self.all_nutcracker:
            m.args['cluster_name'] = args['cluster_name']

    def _rewrite_redis_config(self):
        #make pairs
        for i in range(len(self.args['redis'])):
            r = self.args['redis'][i]
            if len(r) == 2: #old format ('127.0.0.5:22000', '/tmp/r/redis-22000')
                host, port = r[0].split(':')
                path = r[1]
                if i % 2 == 1: # is slave, use port of last one
                    master_port = self.args['redis'][i-1].split(':')[2]
                else:
                    master_port = port
                s = '%s-%s:%s:%s:%s' % (self.args['cluster_name'], master_port, host, port, path)
                self.args['redis'][i] = s
            else:
                self.args['redis'][i] = s

        #merge the 'migration' section
        if 'migration' in  self.args:
            for migration in self.args['migration']:
                src, dst = migration.split('=>')
                for i in range(len(self.args['redis'])):
                    if self.args['redis'][i] == src:
                        self.args['redis'][i] = dst
                        logging.info('replace %s as %s' % (src, dst))

        pprint(self.args)

    def _make_redis(self, spec):
        server_name, host, port, path = spec.split(':')
        host_port = host+':'+port
        #port = int(port)

        r = RedisServer(self.args['user'], host_port, path)
        r.args['cluster_name'] = self.args['cluster_name']
        r.args['server_name'] = server_name
        return r

    def _find_redis(self, host_port, name): # make master instance
        #TODO, remove name
        host = host_port.split(':')[0]
        port = int(host_port.split(':')[1])
        for r in self.all_redis:
            if r.args['host'] == host and r.args['port'] == port:
                return r
        #TODO: if not found, construct one

    def _doit(self, op):
        logging.notice('%s redis' % (op, ))
        for s in self.all_redis:
            eval('s.%s()' % op)

        logging.notice('%s sentinel' % (op, ))
        for s in self.all_sentinel:
            eval('s.%s()' % op)

        logging.notice('%s nutcracker' % (op, ))
        for s in self.all_nutcracker:
            eval('s.%s()' % op)

    def _get_available_sentinel(self):
        for s in self.all_sentinel:
            if s._alive():
                return s
        logging.warn('No sentinel instance are available')
        return None

    def _active_masters(self):
        '''return the current master list on sentinel'''
        new_masters = self._get_available_sentinel().get_masters()
        new_masters = sorted(new_masters, key=lambda x: x[1])

        masters = [self._find_redis(host_port, name) for host_port, name in new_masters]
        return masters

    def deploy(self):
        '''
        deploy the binarys and config file (redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('deploy')

    def start(self):
        '''
        start all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('start')

        #TODO: if any master/slave relation is already setup, we will not do this(sentinel will do this)
        logging.notice('setup master <- slave')
        rs = self.all_redis
        pairs = [rs[i:i+2] for i in range(0, len(rs), 2)]
        for m, s in pairs:
            if s.isslaveof(m.args['host'], m.args['port']) or m.isslaveof(s.args['host'], s.args['port']):
                logging.warn('%s <- %s is ok!' % (m,s ))
            else:
                logging.info('setup %s <- %s' % (m,s ))
                s.slaveof(m.args['host'], m.args['port'])

    def stop(self):
        '''
        stop all instance(redis/sentinel/nutcracker) in this cluster
        '''
        if 'yes' == raw_input('do you want to stop yes/no: '):
            self._doit('stop')

    def printcmd(self):
        '''
        print the start/stop cmd of instance
        '''
        self._doit('printcmd')

    def status(self):
        '''
        get status of all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('status')
        sentinel = self._get_available_sentinel()
        logging.notice('status master-slave')

        def formatslave(s):
            ret = '%s:%s' % (s['ip'], s['port'])
            if s['is_disconnected']:
                return common.to_red(ret)
            return ret

        #print self._active_masters()
        for m in self._active_masters():
            slaves = [formatslave(s) for s in sentinel.get_slaves(m.args['server_name'])]
            print m.args['server_name'], m, '<-', '/'.join(slaves)


    def log(self):
        '''
        show log of all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('log')

    def _rediscmd(self, cmd, sleeptime=.1):
        for s in self.all_redis:
            time.sleep(sleeptime)
            s.rediscmd(cmd)

    def rediscmd(self, cmd):
        '''
        run redis command against all redis instance, like 'INFO, GET xxxx'
        '''
        self._rediscmd(cmd)

    def mastercmd(self, cmd):
        '''
        run redis command against all redis Master instance, like 'INFO, GET xxxx'
        '''
        for s in self._active_masters():
            s.rediscmd(cmd)

    def rdb(self):
        '''
        do rdb in all redis instance,
        '''
        self._rediscmd('BGSAVE', conf.RDB_SLEEP_TIME)

        t = common.format_time(None, '%Y%m%d%H')
        cmd = 'cp data/dump.rdb data/dump.rdb.%s' % t
        for s in self.all_redis:
            s._sshcmd(cmd)

    def aof_rewrite(self):
        '''
        do aof_rewrite in all redis instance
        '''
        self._rediscmd('BGREWRITEAOF', conf.RDB_SLEEP_TIME)

    def randomkill(self):
        '''
        random kill master every mintue (for test failover)
        '''
        while True:
            r = random.choice(self._active_masters())
            logging.notice('will restart %s' % r)
            r.stop()
            time.sleep(80)
            r.start()
            time.sleep(60)

    def sshcmd(self, cmd):
        '''
        ssh to target machine and run cmd
        '''
        hosts = [s.args['host'] for s in self.all_redis + self.all_sentinel + self.all_nutcracker]
        hosts = set(hosts)

        args = copy.deepcopy(self.args)
        args['cmd'] = cmd
        for h in hosts:
            args['host'] = h
            cmd = TT('ssh -n -f $user@$host "$cmd"', args)
            print common.system(cmd)

    def reconfigproxy(self):
        '''
        sync the masters list from sentinel to proxy
        '''
        logging.notice('begin reconfigproxy')
        old_masters = self.all_nutcracker[0].get_masters()
        new_masters = self._get_available_sentinel().get_masters()
        logging.info("old masters: %s" % sorted(old_masters, key=lambda x: x[1]))
        logging.info("new masters: %s" % sorted(new_masters, key=lambda x: x[1]))

        if set(new_masters) == set(old_masters):
            logging.notice('masters list of proxy are already newest, we will not do reconfigproxy')
            return
        logging.notice('we will do reconfigproxy')

        masters = self._active_masters()
        for m in self.all_nutcracker:
            m.reconfig(masters)
        logging.notice('reconfig all nutcracker Done!')

    def failover(self):
        '''
        catch failover event and update the proxy configuration
        '''
        while True:
            try:
                sentinel = self._get_available_sentinel()
                for event in sentinel.get_failover_event():
                    self.reconfigproxy()
            except Exception, e:
                logging.warn('we got exception: %s on failover task' % e)
                logging.exception(e)

def discover_op():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m[0] for m in methods if not m[0].startswith('_')]
    return sets

def gen_op_help():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m for m in methods if not m[0].startswith('_')]

    #sort the function list, based on the their position in the files
    lines = file('bin/deploy.py').readlines() + file('lib/monitor.py').readlines()
    def rank(x):
        name, func = x
        t = 'def ' + name
        for i in range(len(lines)):
            if strstr(lines[i], t):
                return i
    sets = sorted(sets, key=rank)

    def format_func(name, func):
        args, _a, _b, defaults = inspect.getargspec(func)

        specs = []
        if defaults:
            firstdefault = len(args) - len(defaults)
        for i, arg in enumerate(args):
            if defaults and i >= firstdefault:
                spec = '[' + arg + ']' # optional args
            else:
                spec = arg
            specs.append(spec)

        specs = ' '.join(specs[1:])
        if spec:
            desc = '%s %s' % (name, specs)
        else:
            desc = name
        return '%-25s: %s' % (common.to_blue(desc), str(func.__doc__).strip())

    return '\n'.join([format_func(name, func) for name, func in sets])

def discover_cluster():
    sets = [s for s in dir(conf) if s.startswith('cluster')]
    return sets

def main():
    sys.argv.insert(1, '-v') # force -v
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument('target', metavar='clustername', choices=discover_cluster(), help=' / '.join(discover_cluster()))
    parser.add_argument('op', metavar='op', choices=discover_op(),
        help=gen_op_help())
    parser.add_argument('cmd', nargs='*', help='the redis/ssh cmd like "INFO"')

    LOGPATH = os.path.join(WORKDIR, 'log/deploy.log')
    args = common.parse_args2(LOGPATH, parser)
    common.update_logging_level(logging.root, logfile_level=logging.DEBUG)
    if args.cmd:
        eval('Cluster(conf.%s).%s(%s)' % (args.target, args.op, '*args.cmd') )
    else:
        eval('Cluster(conf.%s).%s()' % (args.target, args.op) )

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
