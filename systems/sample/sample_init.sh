#!/bin/bash

pkill -f 'java.*zoo*'
CURR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf log*
rm -rf trace*
rm -rf workload_dir0*
mkdir workload_dir0
touch workload_dir0/foo
dd if=/dev/urandom of=./workload_dir0/foo bs=4k count=2