#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooRetry

remote_user_name = 'aishwarya'
cords_dir = '/home/aishwarya/CORDS'
workload_home = cords_dir + '/systems/remote_zk/'

#ZooKeeper code home, log file names
zk_home = '/home/aishwarya/zookeeper/'
servers = ['0', '1', '2']

ips = {}
ips['0'] = 'c220g1-030825.wisc.cloudlab.us'
ips['1'] = 'c220g1-030828.wisc.cloudlab.us'
ips['2'] = 'c220g1-030829.wisc.cloudlab.us'

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 	stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

def invoke_remote_cmd(machine_ip, command):
	cmd = 'ssh {0}@{1} \'{2}\''.format(remote_user_name, machine_ip, command)
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 	stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

def run_remote(machine_ip, command):
	cmd = 'ssh {0}@{1} \'{2}\''.format(remote_user_name, machine_ip, command)
	os.system(cmd)

def copy_file_remote(machine_ip, from_file_path, to_file_path):
	cmd = 'scp {0} {1}@{2}:{3}'.format(from_file_path, remote_user_name, machine_ip, to_file_path)
	os.system(cmd)

ip_string = ''
for server in servers:
	ip_string += 'server.' + server + '={0}'.format(ips[server]) + ':2888:3888' + '\n'

#ZooKeeper-related Config
logging.basicConfig()
conf_string = '''tickTime=2000
dataDir={0}
clientPort=2181
initLimit=5
syncLimit=2''' + '''\n''' + ip_string + '''preAllocSize=40'''

# Create a clean start state
# Kill Zookeeper
# Delete CORDS trace files
# Delete ZooKeeper workload directories
# Create workload directories
# Create the required files for ZooKeeper
for i in servers:
	cfg_file = '{0}/zoo{1}.cfg'.format(workload_home, str(i))
	cmd = "killall -s 9 java >/dev/null 2>&1; killall -s 9 java >/dev/null 2>&1;"
	cmd += 'rm -rf {0}/debuglogs;'.format(workload_home)
	cmd += 'rm -rf {0}/trace*;'.format(workload_home)
	cmd += 'rm -rf {0}/workload_dir{1}*;'.format(workload_home, i)
	cmd += 'sleep 1;'
	cmd += "killall -s 9 java >/dev/null 2>&1; killall -s 9 java >/dev/null 2>&1;"
	cmd += 'mkdir -p {0}/debuglogs/{1};'.format(workload_home, i)
	cmd += 'mkdir -p {0}/workload_dir{1};'.format(workload_home, i)
	cmd += 'rm -rf {0};'.format(cfg_file)
	cmd += '''echo {0} > {1}/workload_dir{0}/myid;'''.format(i, workload_home)
	run_remote(ips[i], cmd)

#Start the 3 nodes in the Zookeeper Cluster.
for i in servers:
	command = '''{0}/bin/zkServer.sh start'''.format(zk_home)			
	cfg_file = '{0}/zoo{1}.cfg'.format(workload_home, str(i))
	os.system('rm -rf {0}'.format(cfg_file))
	with open(cfg_file, 'w') as fh:
		fh.write(conf_string.format(workload_home + '/workload_dir' + str(i)))
	copy_file_remote(ips[i], cfg_file, cfg_file)

	remote_command = 'cd {0}/debuglogs/{1};{2} {3} > ./zookeeper.out 2>&1 < /dev/null &'.format(workload_home, str(i), command, cfg_file)
	run_remote(ips[i], remote_command)


os.system('sleep 2')

# Insert key value pairs to ZooKeeper
ALLSERVERS ="{0}:2181,{1}:2181,{2}:2181".format(ips['0'], ips['1'], ips['2'])
returned = None
zk = None
kz_retry = KazooRetry(max_tries=1, delay=0.25, backoff=2)
zk = KazooClient(hosts=ALLSERVERS, connection_retry = kz_retry, command_retry = kz_retry, timeout = 1)
try:
	zk.start()
	returned = zk.create("/zk_test", 'a' * 8192)
	zk.stop()
	print 'Successfully put at server'
except Exception as e:
	print 'Could not put at server'


# Kill all ZooKeeper instances
for i in servers:
	run_remote(ips[i], "killall -s 9 java >/dev/null 2>&1; killall -s 9 java >/dev/null 2>&1;")