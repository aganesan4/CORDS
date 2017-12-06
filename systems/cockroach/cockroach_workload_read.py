#!/usr/bin/env python
import os
import sys
import shutil
import time
import psycopg2
import subprocess
import multiprocessing

CURR_DIR=os.path.dirname(os.path.realpath(__file__))
server_dirs = []
server_logs = []
log_dir = None

assert len(sys.argv) >= 4
for i in range(1, 4):
	server_dirs.append(sys.argv[i]) 

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

#if logdir specified
if len(sys.argv) == 5:
	log_dir = sys.argv[-1]

	for i in range(0, 3):
		server_logs.append(os.path.join(log_dir, 'log-'+ str(i)))
		os.system('rm -rf '+ os.path.join(log_dir, 'log-'+ str(i)))
		os.system('mkdir '+ os.path.join(log_dir, 'log-'+ str(i)))
else:
	for i in range(0, 3):
		server_logs.append(os.path.join(CURR_DIR, 'log-'+ str(i)))
		os.system('rm -rf '+ os.path.join(CURR_DIR, 'log-'+ str(i)))
		os.system('mkdir '+ os.path.join(CURR_DIR, 'log-'+ str(i)))

os.system('killall cockroach')
os.system('killall cockroach')
os.system('killall cockroach')

time.sleep(3)

COCKROACH_HOME='/mnt/data1/scratch/work/adsl-work/d2s/applications/cockroach/cockroach-beta-20160714.linux-amd64'

os.system('%s/cockroach start --store=%s --log-dir=%s &'%(COCKROACH_HOME, server_dirs[0], server_logs[0]))
os.system('%s/cockroach start --store=%s --log-dir=%s --port=26258 --http-port=8081 --join=localhost:26257 --join=localhost:26259 &'%(COCKROACH_HOME, server_dirs[1], server_logs[1]))
os.system('%s/cockroach start --store=%s --log-dir=%s --port=26259 --http-port=8082 --join=localhost:26257 --join=localhost:26258 &'%(COCKROACH_HOME, server_dirs[2], server_logs[2]))

time.sleep(2)

def logger_log(log_dir, str):
	if log_dir is not None:
		assert os.path.isdir(log_dir) and os.path.exists(log_dir)
		client_log_file = os.path.join(log_dir, 'log-client')
		with open(client_log_file, 'a') as f:
			f.write(str)
	else:
		print(str.replace('\n', ';'))

before_status = [False, False, False]
logger_log(log_dir, 'Before workload\n')
out, err = invoke_cmd('ps aux | grep cockroach-beta-20160714.linux-amd64')
print out, err
to_write = ''
out = out.split('\n')
out = [i for i in out if i is not None and len(i) > 0 and ('workload_dir0' in i or 'workload_dir1' in i or 'workload_dir2' in i)]
to_check = ['workload_dir0', 'workload_dir1', 'workload_dir2']
j = 0
for check in to_check:
	found = False
	for i in out:
		if check in i:
			found = True
	to_write += check.replace('workload_dir', 'node') + ' running:' + str(found) + '\n'
	before_status[j] = found
	j += 1

logger_log(log_dir, to_write)
logger_log(log_dir, '----------------------------------------------\n')

def do_work(server_id, port):
	inited_value = 'a' * 8192
	retry = 0
	while(retry < 3):
		try:
			logger_log(log_dir, 'Connecting to ' + str(server_id) + ' at port:' + str(port) + '\n')
			conn = psycopg2.connect(host="localhost", port=port, database = "mydb", user="root", connect_timeout=5)
			logger_log(log_dir, 'Connected to ' + str(server_id)+ '\n')

			conn.set_session(autocommit=True)
			cur = conn.cursor()
			cur.execute("SELECT * FROM mytable;")
			logger_log(log_dir, 'Executed on ' + str(server_id)+ '\n')

			result = []

			for record in cur:
				result.append(record)
	
			logger_log(log_dir, 'Server:' + str(server_id) + ' Record count:' + str(len(result)) + '\n')
			for r in result:
				logger_log(log_dir, 'Server:' + str(server_id) +  ' Correct value present:' + str(len(r) == 2 and r[0] == 1 and inited_value == str(r[1])) + '\n')
				if not (len(r) == 2 and r[0] == 1 and inited_value == str(r[1])):
					logger_log(log_dir, 'Server:' + str(server_id) +  ' Value returned:' + str(r) + '\n')
			
			cur.close()
			conn.close()
			break #if executed successfully just break
		except Exception as e:
			retry += 1	
			logger_log(log_dir, 'Server:' + str(server_id) + ' Exception:' + str(e) + '\n')
			time.sleep(1)

server_ports = ["26257", "26258", "26259"]
for i in range(0, len(server_ports)):
	if before_status[i] == True:
		high_level_retry = 0
		while high_level_retry <= 1:
			p = multiprocessing.Process(target=do_work, args=(i, server_ports[i],))
			p.start()
			p.join(25)

			if p.is_alive():
				p.terminate()
				p.join()
				logger_log(log_dir, 'HLT: '+ str(high_level_retry) +' Worker thread for server:'+ str(i)+ ' killed after 25 seconds!\n')
				high_level_retry += 1
			else:
				break
	else:
		logger_log(log_dir, 'Server ' + str(i) + ' is not running. So will not connect.\n')

logger_log(log_dir, '----------------------------------------------\n')
logger_log(log_dir, 'After workload\n')
out, err = invoke_cmd('ps aux | grep cockroach-beta-20160714.linux-amd64')
to_write = ''
out = out.split('\n')
out = [i for i in out if i is not None and len(i) > 0 and ('workload_dir0' in i or 'workload_dir1' in i or 'workload_dir2' in i)]
to_check = ['workload_dir0', 'workload_dir1', 'workload_dir2']
for check in to_check:
	found = False
	for i in out:
		if check in i:
			found = True
	to_write += check.replace('workload_dir', 'node') + ' running:' + str(found) + '\n'

logger_log(log_dir, to_write)
		
os.system('killall cockroach')
os.system('killall cockroach')
os.system('killall cockroach')
time.sleep(1)