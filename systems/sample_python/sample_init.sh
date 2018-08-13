#!/bin/bash

CURR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf $CURR_DIR/log*
rm -rf $CURR_DIR/trace*
rm -rf $CURR_DIR/workload_dir0*
mkdir $CURR_DIR/workload_dir0
echo 'test' > $CURR_DIR/workload_dir0/foo