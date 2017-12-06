#!/usr/bin/env python
import os
import sys
import shutil
import time
import psycopg2

COCKROACH_HOME='/mnt/data1/scratch/work/adsl-work/d2s/applications/cockroach/cockroach-beta-20160714.linux-amd64'
CURR_DIR=os.path.dirname(os.path.realpath(__file__))

def stop_cluster():
	# No -s 9!
	os.system('killall cockroach')
	# just one killall is enough 
	os.system('killall cockroach')
	os.system('killall cockroach')

stop_cluster()
time.sleep(3)

os.system('rm -rf workload_dir*;rm -rf log*;rm -rf trace*')
os.mkdir('%s/workload_dir0'%(CURR_DIR))
os.mkdir('%s/workload_dir1'%(CURR_DIR))
os.mkdir('%s/workload_dir2'%(CURR_DIR))

os.mkdir(os.path.join(CURR_DIR, 'log-0'))
os.mkdir(os.path.join(CURR_DIR, 'log-1'))
os.mkdir(os.path.join(CURR_DIR, 'log-2'))

os.system('%s/cockroach start --store=%s/workload_dir0 --log-dir=%s &'%(COCKROACH_HOME, CURR_DIR, os.path.join(CURR_DIR, 'log-0')))
time.sleep(2)

# join the first started node by specifying the --join flag:
# see here: https://forum.cockroachlabs.com/t/right-way-to-start-a-cockroachdb-cluster/256

os.system('%s/cockroach start --store=%s/workload_dir1 --log-dir=%s --port=26258 --http-port=8081 --join=localhost:26257 &'%(COCKROACH_HOME, CURR_DIR, os.path.join(CURR_DIR, 'log-1')))
os.system('%s/cockroach start --store=%s/workload_dir2 --log-dir=%s --port=26259 --http-port=8082 --join=localhost:26257 --join=localhost:26258 &'%(COCKROACH_HOME, CURR_DIR, os.path.join(CURR_DIR, 'log-2')))

time.sleep(3)

# just any buffer...Will be easy to grep if we know the pattern
value='a' * 8192 

create_command = 'CREATE DATABASE mydb;'
command =  COCKROACH_HOME + '/cockroach sql -e \'' + create_command + '\''
os.system(command)

time.sleep(1)
conn = psycopg2.connect(host="localhost", port="26257", database = "mydb", user="root")
cur = conn.cursor()
cur.execute("CREATE TABLE mytable (id int PRIMARY KEY, data varchar);")
cur.execute("INSERT INTO mytable (id, data) VALUES (%s, %s)",(1, value))
conn.commit()
cur.close()
conn.close()

time.sleep(1)
stop_cluster()
time.sleep(2)