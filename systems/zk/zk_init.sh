#!/bin/bash

pkill -f 'java.*zoo*'
ZK_HOME='/mnt/data1/scratch/work/adsl-work/d2s/applications/zookeeper-3.4.8/'
CURR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf cordslog*
rm -rf trace*
rm -rf workload_dir0*
mkdir workload_dir0

rm -rf workload_dir1*
mkdir workload_dir1

rm -rf workload_dir2*
mkdir workload_dir2

touch workload_dir0/myid
touch workload_dir1/myid
touch workload_dir2/myid

echo '1' > workload_dir0/myid
echo '2' > workload_dir1/myid
echo '3' > workload_dir2/myid

$ZK_HOME/bin/zkServer.sh start $CURR_DIR/zoo0.cfg 
$ZK_HOME/bin/zkServer.sh start $CURR_DIR/zoo1.cfg 
$ZK_HOME/bin/zkServer.sh start $CURR_DIR/zoo2.cfg 


value=$(printf 'a%.s' {1..8192})
echo 'create /zk_test '$value > script

$ZK_HOME"/bin/zkCli.sh" -server 127.0.0.2:2182 < script
sleep 1

rm -rf script
pkill -f 'java.*zoo*'
ps aux | grep zoo
rm -rf zookeeper.out