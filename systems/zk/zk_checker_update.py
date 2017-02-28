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

assert len(sys.argv) == 2
to_check_base_dir = sys.argv[1]

for i in range(0, 3):
	server_dirs.append(os.path.join(to_check_base_dir, 'workload_dir' + str(i))) 

print server_dirs

content = None
with open(os.path.join(to_check_base_dir, 'log-client'), 'r') as f:
	content = f.read()

client_acked = False
if 'Successfully put' in content:
	client_acked = True

# For now assume only 3 nodes
server_config0 = (config_info) % (server_dirs[0], port_list[0], )
server_config1 = (config_info) % (server_dirs[1], port_list[1], )
server_config2 = (config_info) % (server_dirs[2], port_list[2], )

config_files = [ os.path.join('/tmp', 'zoo0.check.cfg'), os.path.join('/tmp', 'zoo1.check.cfg'), os.path.join('/tmp', 'zoo2.check.cfg')]
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

out = 'ACK:' + str(client_acked) + ' '
err = ''
time.sleep(2)
updated_value = 'b' * 8192

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
		out += 'Got at server' + str(server_index - 1) + ' Proper:' + str(returned == updated_value)
		break
	except Exception as e:
		err += 'Could not get at server ' + str(server_index - 1) + '\t:' + str(e) + '\n' 

check_res_file = os.path.join(to_check_base_dir, 'checkres')
with open(check_res_file, 'w') as f:
	f.write('out:\n' + str(out) + '\n')
	f.write('err:\n' + str(err) + '\n')
	
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")
os.system("pkill -f \'java.*zoo*\'")
time.sleep(1)
os.system('rm -rf ' + config_files[0])
os.system('rm -rf ' + config_files[1])
os.system('rm -rf ' + config_files[2]) 