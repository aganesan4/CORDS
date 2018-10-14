#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
import rethinkdb as r

logging.basicConfig()

CURR_DIR = os.path.dirname(os.path.realpath(__file__))

os.system('docker rm $(docker stop -t 0 $(docker ps -aq)) > /dev/null')
server_dirs = []
server_logs = []
server_logs_host = []
log_dir = None

assert len(sys.argv) >= 4
for i in range(2, 5):
	server_dirs.append(sys.argv[i]) 

#if logdir specified
if len(sys.argv) == 6:
	log_dir = sys.argv[-1]


def logger_log(log_dir, str):
	if log_dir is not None:
		assert os.path.isdir(log_dir) and os.path.exists(log_dir)
		client_log_file = os.path.join(log_dir, 'log-client')
		with open(client_log_file, 'a') as f:
			f.write(str)
	else:
		print(str.replace('\n', ';'))

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

server_dirs = []
log_dir = None

assert len(sys.argv) >= 4
for i in range(2, 5):
	server_dirs.append(sys.argv[i]) 

#if logdir specified
if len(sys.argv) == 6:
	log_dir = sys.argv[-1]

uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])


CORDS_HOME = '/home/ram/CORDS'

master_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag master --directory %s --bind all --log-file %s'
slave1_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --directory %s --bind all --log-file %s'
slave2_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --join %s:29015 --directory %s --bind all --log-file %s'

get_ip_cmd = 'docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' %s'

for i in range(0, len(server_dirs)):
	server_logs_host.append(os.path.join(uppath(server_dirs[i],1), 'log-' + str(i)))
	server_dirs[i] = server_dirs[i].replace(CORDS_HOME, '/appdir')
	server_logs.append(os.path.join(uppath(server_dirs[i],1), 'log-' + str(i)))

assert len(server_dirs) == 3

master_start_command = master_start_command%(CORDS_HOME, server_dirs[0], server_logs[0])
master_cid, err = invoke_cmd(master_start_command)
master_cid = master_cid.strip().replace('\n', '')
assert master_cid is not None
assert err is None or len(err) == 0

master_ip, err = invoke_cmd(get_ip_cmd%(master_cid))
master_ip = master_ip.strip().replace('\n', '')
assert master_ip is not None
assert err is None or len(err) == 0

slave1_start_command = slave1_start_command%(CORDS_HOME, 'slave1', master_ip, server_dirs[1], server_logs[1])
slave1_cid, err =  invoke_cmd(slave1_start_command)
slave1_cid = slave1_cid.strip().replace('\n', '')
assert slave1_cid is not None
assert err is None or len(err) == 0

slave1_ip, err = invoke_cmd(get_ip_cmd%(slave1_cid))
slave1_ip = slave1_ip.strip().replace('\n', '')
assert slave1_ip is not None
assert err is None or len(err) == 0

slave2_start_command = slave2_start_command%(CORDS_HOME, 'slave2', master_ip, slave1_ip, server_dirs[2], server_logs[2])
slave2_cid, err =  invoke_cmd(slave2_start_command)
slave2_cid = slave2_cid.strip().replace('\n', '')
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

cids = []
cids.append(master_cid)
cids.append(slave1_cid)
cids.append(slave2_cid)

should_try_connect = [False, False, False]

# All nodes have started! Do the workload.
time.sleep(5)
out = ''
err = ''
inited_value = 'a' * 8192

server_i = 0
for server_ip in server_ips:
	proc_command = 'docker exec %s ps aux | grep rethink'%cids[server_i]
	out2,err2 = invoke_cmd(proc_command)
	processes = out2.split('\n')
	processes = [p for p in processes if len(p) > 0]
	should_try_connect[server_i] = False
	if len(processes) >= 2:
		for process in processes:
			if 'rethinkdb' in process and server_dirs[server_i] in process:
				should_try_connect[server_i] = True

	server_i += 1

server_i = 0
logger_log(log_dir, 'Before workload\n')
to_write = ''
for server_ip in server_ips:
	to_write += 'Server ' + str(server_ip) + ' running:' + str(should_try_connect[server_i]) + '\n'
	server_i += 1

logger_log(log_dir, to_write)
logger_log(log_dir, '----------------------------------------------\n')

server_i = 0

out = ''
for server_ip in server_ips:
	if should_try_connect[server_i]:
		try:
			r.connect(server_ip, 28015).repl()		
			document = r.table("products", read_mode= 'majority').get('myprimarykey').run()

			if document is not None and len(document) > 0:
				if inited_value in str(document):
					out += 'Successfully read the value at server:' + str(server_ip) + ' !\n' 
				else:
					out += 'Problem at server:' + str(server_ip) + '- Corrupted Value!\n'
					out += str(document) + '\n'
			else:
				out += 'Problem at server:' + str(server_ip) + '- Document not retrieved!\n'
				out += str(document) + '\n'
			break
		except Exception as e:
			err += 'Exception occured:' + str(e) + ' at server:' + str(server_ip) + '\n'
			time.sleep(5)
	else:
		out += 'Server' + str(server_i) +' not running. Not connecting\n'

	server_i += 1

logger_log(log_dir, out)
logger_log(log_dir, err)

after_status = [False, False, False]
server_i = 0
for server_ip in server_ips:
	proc_command = 'docker exec %s ps aux | grep rethink'%cids[server_i]
	out2,err2 = invoke_cmd(proc_command)
	processes = out2.split('\n')
	processes = [p for p in processes if len(p) > 0]
	after_status[server_i] = False
	if len(processes) >= 2:
		for process in processes:
			if 'rethinkdb' in process and server_dirs[server_i] in process:
				after_status[server_i] = True

	server_i += 1

logger_log(log_dir, '----------------------------------------------\n')

server_i = 0
logger_log(log_dir, 'After workload\n')
to_write = ''
for server_ip in server_ips:
	to_write += 'Server ' + str(server_ip) + ' running:' + str(after_status[server_i]) + '\n'
	server_i += 1

logger_log(log_dir, to_write)
logger_log(log_dir, '----------------------------------------------\n')

# if log_dir specified
if log_dir is not None:
	for i in range(0, len(server_dirs)):
		os.system('mv ' + server_logs_host[i]  + ' ' + os.path.join(log_dir, 'log-'+str(i)))

os.system('docker rm $(docker stop -t 0 $(docker ps -aq)) > /dev/null')