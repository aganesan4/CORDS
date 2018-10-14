#!/usr/bin/env  python

import sys
import os
import time
import subprocess
import logging
import rethinkdb as r

logging.basicConfig()

CURR_DIR = os.path.dirname(os.path.realpath(__file__))

os.system('docker rm $(docker stop -t 0 $(docker ps -aq))')
os.system('rm -rf trace*')

os.system('rm -rf workload_dir0*')
os.system('mkdir workload_dir0')

os.system('rm -rf workload_dir1*')
os.system('mkdir workload_dir1')

os.system('rm -rf workload_dir2*')
os.system('mkdir workload_dir2')

server_dirs = ['/appdir/systems/rethinkdb/workload_dir0', '/appdir/systems/rethinkdb/workload_dir1', '/appdir/systems/rethinkdb/workload_dir2']

def invoke_cmd(cmd):
	p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	return (out, err)

CORDS_HOME = '/home/ram/CORDS'

master_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag master --directory %s --bind all --log-file /dev/null'
slave1_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --directory %s --bind all --log-file /dev/null'
slave2_start_command = 'docker run -d -v %s:/appdir -it --entrypoint=rethinkdb ramanala/ubuntu2 --server-tag %s --join %s:29015 --join %s:29015 --directory %s --bind all --log-file /dev/null'

get_ip_cmd = 'docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' %s'

master_start_command = master_start_command%(CORDS_HOME, server_dirs[0],)
master_cid, err = invoke_cmd(master_start_command)
master_cid = master_cid.strip().replace('\n', '')
assert master_cid is not None
assert err is None or len(err) == 0

master_ip, err = invoke_cmd(get_ip_cmd%(master_cid))
master_ip = master_ip.strip().replace('\n', '')
assert master_ip is not None
assert err is None or len(err) == 0

slave1_start_command = slave1_start_command%(CORDS_HOME, 'slave1', master_ip, server_dirs[1])
slave1_cid, err = invoke_cmd(slave1_start_command)
slave1_cid = slave1_cid.strip().replace('\n', '')
assert slave1_cid is not None
assert err is None or len(err) == 0

slave1_ip, err = invoke_cmd(get_ip_cmd%(slave1_cid))
slave1_ip = slave1_ip.strip().replace('\n', '')
assert slave1_ip is not None
assert err is None or len(err) == 0

slave2_start_command = slave2_start_command%(CORDS_HOME, 'slave2', master_ip, slave1_ip, server_dirs[2])
invoke_cmd(slave2_start_command)

# All nodes have started! Do the init.
time.sleep(10)
value = 'a' * 8192
out = ''
err = ''

try:
	r.connect(master_ip, 28015).repl()
	r.db('test').table_create('products', shards = 1, replicas = {'master': 1, 'slave1': 1, 'slave2': 1}, primary_replica_tag = 'master').run()
	r.table('products').insert({ 'id': 'myprimarykey', 'value' : value }).run()	
	out = 'Successfully inserted!'
except Exception as e:
	err = 'Exception occured:' + str(e)

print out, err
os.system('docker rm $(docker stop -t 0 $(docker ps -aq))')