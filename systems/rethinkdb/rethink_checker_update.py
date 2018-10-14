#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
import rethinkdb as r

logging.basicConfig()

CURR_DIR = os.path.dirname(os.path.realpath(__file__))
CORDS_HOME = '/mnt/data1/corrupt-ds-apps'

uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])

os.system('docker rm $(docker stop -t 0 $(docker ps -aq)) > /dev/null')
server_dirs = []
log_dir = None

assert len(sys.argv) == 2
to_check_base_dir = sys.argv[1]

replay_dir_base = uppath(to_check_base_dir, 1)
for i in range(0, 3):
	server_dirs.append(os.path.join(to_check_base_dir, 'workload_dir' + str(i))) 

for i in range(0, 3):
	server_dirs[i] = server_dirs[i].replace(replay_dir_base, '/appdir/')

content = None
with open(os.path.join(to_check_base_dir, 'log-client'), 'r') as f:
	content = f.read()

client_acked = False
if 'Successfully updated' in content:
	client_acked = True

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

master_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag master --directory %s --bind all --log-file /dev/null'
slave1_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --directory %s --bind all --log-file /dev/null'
slave2_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --join %s:29015 --directory %s --bind all --log-file /dev/null'

get_ip_cmd = 'docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' %s'
assert len(server_dirs) == 3

master_start_command = master_start_command%(replay_dir_base, server_dirs[0])
master_cid, err = invoke_cmd(master_start_command)
master_cid = master_cid.strip().replace('\n', '')
assert master_cid is not None
assert err is None or len(err) == 0

master_ip, err = invoke_cmd(get_ip_cmd%(master_cid))
master_ip = master_ip.strip().replace('\n', '')
assert master_ip is not None
assert err is None or len(err) == 0

slave1_start_command = slave1_start_command%(replay_dir_base, 'slave1', master_ip, server_dirs[1])
slave1_cid, err =  invoke_cmd(slave1_start_command)
assert slave1_cid is not None
assert err is None or len(err) == 0

slave1_ip, err = invoke_cmd(get_ip_cmd%(slave1_cid))
slave1_ip = slave1_ip.strip().replace('\n', '')
assert slave1_ip is not None
assert err is None or len(err) == 0

slave2_start_command = slave2_start_command%(replay_dir_base, 'slave2', master_ip, slave1_ip, server_dirs[2])
slave2_cid, err =  invoke_cmd(slave2_start_command)
assert slave2_cid is not None
assert err is None or len(err) == 0

slave2_ip, err = invoke_cmd(get_ip_cmd%(slave2_cid))
slave2_ip = slave2_ip.strip().replace('\n', '')
assert slave2_ip is not None
assert err is None or len(err) == 0

server_ips = []
server_ips.append(master_ip)
server_ips.append(slave1_ip)
server_ips.append(slave2_ip)

# All nodes have started! Do the check.
out = 'ACK:' + str(client_acked) + ' '
err = ''
time.sleep(3)
updated_value = 'b' * 8192

for server_ip in server_ips:
	try:
		r.connect(server_ip, 28015).repl()		
		document = r.table("products", read_mode= 'majority').get('myprimarykey').run()

		if document is not None and len(document) > 0:
			if updated_value in str(document):
				out = 'Successfully read the value at server:' + str(server_ip) + ' !' 
			else:
				out = 'Problem at server:' + str(server_ip) + ' !'
		else:
			out = 'Problem at server:' + str(server_ip) + ' !'

		print out
		break
	except Exception as e:
		err += 'Exception occured:' + str(e) + ' at server:' + str(server_ip) + '\n'

check_res_file = os.path.join(to_check_base_dir, 'checkres')
with open(check_res_file, 'w') as f:
	f.write('out:\n' + str(out) + '\n')
	f.write('err:\n' + str(err) + '\n')
	
time.sleep(1)
os.system('docker rm $(docker stop -t 0 $(docker ps -aq)) > /dev/null')
