#!/usr/bin/env  python
import sys
import os

CURR_DIR = os.path.dirname(os.path.realpath(__file__))
if sys.argv[1] == 'trace':
	print 'we are in trace mode now'
	assert(len(sys.argv) == 3)
	# format of sys.argv is sample_read.py trace workload_dir
elif sys.argv[1] == 'cords':
	print 'we are in cords mode now, injecting faults'
	assert(len(sys.argv) == 4)
	# format of sys.argv is sample_read.py cords workload_dir result_dir
workload_dir = sys.argv[2]
file = open(workload_dir + '/foo', 'r')
status = ''
try:
	read_data = (file.read())
	file.close()
	if read_data == 'test\n':
		status = 'Correct'
		print status
	else:
		status = 'Corrupt'
		print status
except Exception as e:
	print 'Error:' + str(e)
	status = 'Error'
if sys.argv[1] == 'cords':
	result_dir = sys.argv[-1]
	# you can copy any files you need into this result_dir like application logs etc., or log additional data
	f = open(result_dir + '/status' , 'w')
	f.write(status)
	f.close()