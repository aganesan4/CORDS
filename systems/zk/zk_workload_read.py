#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooRetry

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

#ZooKeeper-related Config
logging.basicConfig()
host_list = ['127.0.0.2', '127.0.0.3', '127.0.0.4']
port_list = [2182, 2183, 2184]
config_info = '''tickTime=2000\ndataDir=%s\nclientPort=%s\ninitLimit=5\nsyncLimit=2\nserver.1=127.0.0.2:2888:3888\nserver.2=127.0.0.3:2889:3889\nserver.3=127.0.0.4:2890:3890\npreAllocSize=40'''

#ZooKeeper code home, log file names
ZK_HOME = '~/zookeeper-3.4.12/'
zoo_logfile_name = 'zookeeper.out'

#Kill all Zookeeper Processes
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")

server_dirs = []
log_dir = None

assert len(sys.argv) >= 4

# The CORDS framework passes the following arguments to the workload program
# zk_workload_read.py trace/cords workload_dir1 workload_dir2 .. workload_dirn log_dir

# For ZooKeeper we have three servers and hence three directories
for i in range(2, 5):
	server_dirs.append(sys.argv[i]) 

#if logdir specified
if len(sys.argv) >= 6:
	log_dir = sys.argv[-1]

# For now assume only 3 nodes

# Write the config files with the correct workload directories
server_configs = []
config_files = []
CURR_DIR = os.path.dirname(os.path.realpath(__file__))
for i in [0, 1, 2]:
	server_configs.append((config_info) % (server_dirs[i], port_list[i], ))
	config_files.append((os.path.join(CURR_DIR, 'zoo' + str(i) + '.workload.cfg')))
	with open(config_files[i], 'w') as f:
		f.write(server_configs[i])


# Start the ZooKeeper cluster
for i in [0, 1, 2]:
	# chdir here so that zk can create the log here in this directory
	os.chdir(server_dirs[i]) 
	os.system(os.path.join(ZK_HOME, 'bin/zkServer.sh ') + ('start %s &') % (config_files[i],))
os.chdir(CURR_DIR) 

time.sleep(3)

out = ''
err = ''
present_value = 'a' * 8192 


# Get state of ZooKeeper nodes before reading data
if log_dir is not None:
	client_log_file = os.path.join(log_dir, 'log-client')
	with open(client_log_file, 'w') as f:
		f.write('Before workload\n')
		out, err = invoke_cmd('ps aux | grep zoo')
		to_write = ''
		out = out.split('\n')
		out = [i for i in out if i is not None and len(i) > 0 and ('zoo0.workload.cfg' in i or 'zoo1.workload.cfg' in i or 'zoo2.workload.cfg' in i)]
		to_check = ['zoo0.workload.cfg', 'zoo1.workload.cfg', 'zoo2.workload.cfg']
		for check in to_check:
			found = False
			for i in out:
				if check in i:
					found = True
			to_write += check[:4] + ' running:' + str(found) + '\n'

		f.write(to_write)
		f.write('----------------------------------------------\n')


out = ''
err = ''


# Issue Reads on all the nodes in the cluster and check its value
for server_index in range(1, 4):
	returned = None
	zk = None
	
	connect_string = host_list[server_index-1] + ':' + str(port_list[server_index-1])
	kz_retry = KazooRetry(max_tries=1, delay=0.25, backoff=2)
	zk = KazooClient(hosts=connect_string, connection_retry = kz_retry, command_retry = kz_retry, timeout = 1)
	try:
		zk.start()
		returned, stat = zk.get("/zk_test")
		zk.stop()
		returned = returned.strip().replace('\n', '')
		out += 'Successful get at server ' + str(server_index - 1) + ' Proper:' + str(returned == present_value)  + '\n'
	except Exception as e:
		err += 'Could not get at server ' + str(server_index - 1) + '\t:' + str(e) + '\n' 


print out
print err

# Get state of ZooKeeper nodes after reading data
if log_dir is not None:
	assert os.path.isdir(log_dir) and os.path.exists(log_dir)
	client_log_file = os.path.join(log_dir, 'log-client')
	with open(client_log_file, 'a') as f:
		f.write('out:\n' + str(out) + '\n')
		f.write('err:\n' + str(err) + '\n')
		p = 0
		f.write('CLUSTER STATE:\n')
		for host in host_list:
			out, err = invoke_cmd('echo stat | nc ' + host + ' ' + str(port_list[p]) + ' | grep Mode')	
			f.write(host + ':' + str(port_list[p]) + ':' + out.replace('\n', '') + '|'  + err.replace('\n', '') + '\n')
			p += 1
	
if log_dir is not None:
	client_log_file = os.path.join(log_dir, 'log-client')
	with open(client_log_file, 'a') as f:
		f.write('----------------------------------------------\n')
		f.write('After workload\n')
		out, err = invoke_cmd('ps aux | grep zoo')
		to_write = ''
		out = out.split('\n')
		out = [i for i in out if i is not None and len(i) > 0 and ('zoo0.workload.cfg' in i or 'zoo1.workload.cfg' in i or 'zoo2.workload.cfg' in i)]
		to_check = ['zoo0.workload.cfg', 'zoo1.workload.cfg', 'zoo2.workload.cfg']
		for check in to_check:
			found = False
			for i in out:
				if check in i:
					found = True
			to_write += check[:4] + ' running:' + str(found) + '\n'

		f.write(to_write)

time.sleep(3)
# Kill the ZooKeeper nodes
os.system("pkill -f \'java.*zoo*\'")
time.sleep(1)


os.system("sudo chown -R $USER:$USER workload_dir*")

for i in [0, 1, 2]:
	os.system('rm -rf ' + config_files[i])

# if log_dir specified
if log_dir is not None:
	for i in range(0, len(server_dirs)):
		os.system('cp ' + os.path.join(server_dirs[i], zoo_logfile_name)  + ' ' + os.path.join(log_dir, 'log-'+str(i)))