#! /usr/bin/env python
# Copyright (c) 2016 Aishwarya Ganesan and Ramnatthan Alagappan. 
# All Rights Reserved.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import math
from collections import defaultdict
import subprocess
import argparse

ERRFS_HOME = os.path.dirname(os.path.realpath(__file__))
fuse_command_trace = ERRFS_HOME + "/errfs -f -omodules=subdir,subdir=%s %s trace %s &"

parser = argparse.ArgumentParser()
parser.add_argument('--trace_files', nargs='+', required = True, help = 'Trace file paths')
parser.add_argument('--data_dirs', nargs='+', required = True, help = 'Location of data directories')
parser.add_argument('--workload_command', required = True, type = str)
parser.add_argument('--ignore_file', type = str, default = None)

args = parser.parse_args()
for i in range(0, len(args.trace_files)):
	args.trace_files[i] = os.path.abspath(args.trace_files[i])

for i in range(0, len(args.data_dirs)):
	args.data_dirs[i] = os.path.abspath(args.data_dirs[i])

trace_files = args.trace_files
data_dirs = args.data_dirs
ignore_file = args.ignore_file

assert len(trace_files) == len(data_dirs)
machine_count = len(trace_files)

workload_command = args.workload_command

for data_dir in data_dirs:
	assert os.path.exists(data_dir)

uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])

data_dir_snapshots = []
data_dir_mount_points = []

for i in range(0, machine_count):
	data_dir_snapshots.append(os.path.join(uppath(data_dirs[i], 1), os.path.basename(os.path.normpath(data_dirs[i]))+ ".snapshot"))
	data_dir_mount_points.append(os.path.join(uppath(data_dirs[i], 1), os.path.basename(os.path.normpath(data_dirs[i]))+ ".mp"))
	subprocess.check_output("rm -rf " + data_dir_snapshots[i], shell = True)
	subprocess.check_output("rm -rf " + data_dir_mount_points[i], shell = True)
	subprocess.check_output("mkdir " + data_dir_mount_points[i], shell = True)

for i in range(0, machine_count):
	subprocess.check_output("cp -R " + data_dirs[i] + " " + data_dir_snapshots[i], shell = True)

for i in range(0, machine_count):
	subprocess.check_output("rm -rf " + trace_files[i], shell = True)


for i in range(0, machine_count):
	print fuse_command_trace%(data_dirs[i], data_dir_mount_points[i], trace_files[i])
	os.system(fuse_command_trace%(data_dirs[i], data_dir_mount_points[i], trace_files[i]))

os.system('sleep 1')

workload_command +=  " trace " 
for i in range(0, machine_count):
	workload_command += data_dir_mount_points[i] + " "
os.system(workload_command)

for mp in data_dir_mount_points:
	os.system('fusermount -u ' + mp + '; sleep 1')

os.system('killall errfs >/dev/null 2>&1')

to_ignore_files = []
if ignore_file is not None:	
	with open(ignore_file, 'r') as f:
		for line in f:
			line = line.strip().replace('\n','')
			to_ignore_files.append(line)

def should_ignore(filename):
	for ig in to_ignore_files:
		if ig in filename:
			return True
	return False

for trace_file in trace_files:
	assert os.path.exists(trace_file)
	assert os.stat(trace_file).st_size > 0
	if ignore_file is not None:
		to_write_final = ''
		with open(trace_file, 'r') as f:
			for line in f:
				parts = line.split('\t')
				if parts[0] in ['rename', 'unlink', 'link', 'symlink']:
					to_write_final += line
				else:
					assert len(parts) == 4
					filename = parts[0]
					if not should_ignore(filename):
						to_write_final += line

		os.remove(trace_file)
		with open(trace_file, 'w') as f:
			f.write(to_write_final)

print 'Tracing completed...'