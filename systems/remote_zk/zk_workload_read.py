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
zoo_logfile_name = 'zookeeper.out'

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

def copy_file_to_remote(machine_ip, from_file_path, to_file_path):
	cmd = 'scp {0} {1}@{2}:{3}'.format(from_file_path, remote_user_name, machine_ip, to_file_path)
	os.system(cmd)

def copy_file_from_remote(machine_ip, from_file_path, to_file_path):
	cmd = 'scp {0}@{1}:{2} {3}'.format(remote_user_name, machine_ip, from_file_path, to_file_path)
	os.system(cmd)

#ZooKeeper-related Config
logging.basicConfig()


log_dir = None
servers = ['0', '1', '2']
ips = {}
server_dirs = {}

assert len(sys.argv) >= 7

# The CORDS framework passes the following arguments to the workload program
# zk_workload_read.py trace/cords workload_dir1 workload_dir2 .. workload_dirn remote_ip1 remote_ip2 .. remote_ipn [log_dir]
# For now assume only 3 nodes
for i in range(1, 4):
	ips[str(i-1)] = sys.argv[4 + i]

print ips
ip_string = ''
for server in servers:
	ip_string += 'server.' + server + '={0}'.format(ips[server]) + ':2888:3888' + '\n'

conf_string = '''tickTime=2000
dataDir={0}
clientPort=2181
initLimit=5
syncLimit=2''' + '''\n''' + ip_string + '''preAllocSize=40'''
# For ZooKeeper we have three servers and hence three directories
for i in range(1, 4):
	server_dirs[str(i-1)] = sys.argv[i + 1]

#if logdir specified
if len(sys.argv) >= 9:
	log_dir = sys.argv[-1]

# Kill all ZooKeeper instances on the remote nodes
for i in servers:
	run_remote(ips[i], "killall -s 9 java >/dev/null 2>&1; killall -s 9 java >/dev/null 2>&1;")

# Write the config files with the correct workload directories
for i in servers:
	cfg_file = '{0}/zoo{1}.cfg'.format(workload_home, str(i))
	os.system('rm -rf {0}'.format(cfg_file))
	with open(cfg_file, 'w') as fh:
		fh.write(conf_string.format(server_dirs[i]))
	copy_file_to_remote(ips[i], cfg_file, cfg_file)

#Start the 3 nodes in the Zookeeper Cluster.
for i in servers:
	command = '''{0}/bin/zkServer.sh start'''.format(zk_home)			
	cfg_file = '{0}/zoo{1}.cfg'.format(workload_home, str(i))
	remote_command = 'cd {0};{1} {2} > ./zookeeper.out 2>&1 &'.format(server_dirs[i], command, cfg_file)
	run_remote(ips[i], remote_command)

time.sleep(3)

out = ''
err = ''
present_value = 'a' * 8192 

# Get state of ZooKeeper nodes before reading data
if log_dir is not None:
	client_log_file = os.path.join(log_dir, 'log-client')
	with open(client_log_file, 'w') as f:
		f.write('Before workload\n')
		status = []
		for i in servers:
			out, err = invoke_remote_cmd(ips[i], 'ps aux | grep zoo')
			status.append('zoo' + str(i) + '.cfg' in out)
		f.write(str(status) + '\n')
		f.write('----------------------------------------------\n')

out = ''
err = ''


# Issue Reads on all the nodes in the cluster and check its value
for server_index in range(0, 3):
	returned = None
	zk = None
	connect_string = ips[str(server_index)] + ':2181'
	kz_retry = KazooRetry(max_tries=1, delay=0.25, backoff=2)
	zk = KazooClient(hosts=connect_string, connection_retry = kz_retry, command_retry = kz_retry, timeout = 1)
	try:
		zk.start()
		returned, stat = zk.get("/zk_test")
		zk.stop()
		returned = returned.strip().replace('\n', '')
		out += 'Successful get at server ' + str(server_index) + ' Proper:' + str(returned == present_value)  + '\n'
	except Exception as e:
		err += 'Could not get at server ' + str(server_index) + '\t:' + str(e) + '\n' 

print out
print err

if log_dir is not None:
	client_log_file = os.path.join(log_dir, 'log-client')
	with open(client_log_file, 'a') as f:
		f.write('After workload\n')
		status = []
		for i in servers:
			out, err = invoke_remote_cmd(ips[i], 'ps aux | grep zoo')
			status.append('zoo' + str(i) + '.cfg' in out)
		f.write(str(status) + '\n')
		f.write('----------------------------------------------\n')

# Kill all ZooKeeper instances on the remote nodes
for i in servers:
	run_remote(ips[i], "killall -s 9 java >/dev/null 2>&1; killall -s 9 java >/dev/null 2>&1;")

# if log_dir specified
if log_dir is not None:
	for i in servers:
		copy_file_from_remote(ips[i], os.path.join(server_dirs[i], zoo_logfile_name), os.path.join(log_dir, 'log-'+str(i)))