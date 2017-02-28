#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooRetry

logging.basicConfig()

host_list = ['127.0.0.2', '127.0.0.3', '127.0.0.4']
port_list = [2182, 2183, 2184]

config_info = '''tickTime=2000\ndataDir=%s\nclientPort=%s\ninitLimit=5\nsyncLimit=2\nserver.1=127.0.0.2:2888:3888\nserver.2=127.0.0.3:2889:3889\nserver.3=127.0.0.4:2890:3890'''
ZK_HOME = '/mnt/data1/scratch/work/adsl-work/d2s/applications/zookeeper-3.4.8/'
ZK_HOME_BIN = '/mnt/data1/scratch/work/adsl-work/d2s/applications/zookeeper-3.4.8/bin'
CURR_DIR = os.path.dirname(os.path.realpath(__file__))
zoo_logfile_name = 'zookeeper.out'

os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")

server_dirs = []
log_dir = None

assert len(sys.argv) >= 4
for i in range(1, 4):
	server_dirs.append(sys.argv[i]) 

#if logdir specified
if len(sys.argv) == 5:
	log_dir = sys.argv[-1]

# For now assume only 3 nodes
server_config0 = (config_info) % (server_dirs[0], port_list[0], )
server_config1 = (config_info) % (server_dirs[1], port_list[1], )
server_config2 = (config_info) % (server_dirs[2], port_list[2], )

config_files = [ os.path.join(CURR_DIR, 'zoo0.workload.cfg'), os.path.join(CURR_DIR, 'zoo1.workload.cfg'), os.path.join(CURR_DIR, 'zoo2.workload.cfg')]
with open(config_files[0], 'w') as f:
	f.write(server_config0)

with open(config_files[1], 'w') as f:
	f.write(server_config1)

with open(config_files[2], 'w') as f:
	f.write(server_config2)

node_start0 = os.path.join(ZK_HOME, 'bin/zkServer.sh ') + ('start %s &') % (config_files[0],)
node_start1 = os.path.join(ZK_HOME, 'bin/zkServer.sh ') + ('start %s &') % (config_files[1],)
node_start2 = os.path.join(ZK_HOME, 'bin/zkServer.sh ') + ('start %s &') % (config_files[2],)

# chdir here so that zk can create the log here in this directory
os.chdir(server_dirs[0]) 
os.system(node_start0)

os.chdir(server_dirs[1]) 
os.system(node_start1)

os.chdir(server_dirs[2]) 
os.system(node_start2)

os.chdir(CURR_DIR) 

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

out = ''
err = ''
time.sleep(3)

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

for server_index in range(1, 4):
	returned = None
	zk = None
	
	connect_string = host_list[server_index-1] + ':' + str(port_list[server_index-1])
	kz_retry = KazooRetry(max_tries=1, delay=0.25, backoff=2)
	zk = KazooClient(hosts=connect_string, connection_retry = kz_retry, command_retry = kz_retry, timeout = 1)
	try:
		zk.start()
		returned = zk.set("/zk_test", 'b' * 8192)
		zk.stop()
		out += 'Successfully put at server ' + str(server_index - 1)
		break
	except Exception as e:
		err += 'Could not put at server ' + str(server_index - 1) + '\t:' + str(e) + '\n' 

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
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")
time.sleep(1)
os.system("sudo chown -R ram:ram workload_dir*")
os.system('rm -rf ' + config_files[0])
os.system('rm -rf ' + config_files[1])
os.system('rm -rf ' + config_files[2])

# if log_dir specified
if log_dir is not None:
	for i in range(0, len(server_dirs)):
		os.system('cp ' + os.path.join(server_dirs[i], zoo_logfile_name)  + ' ' + os.path.join(log_dir, 'log-'+str(i)))