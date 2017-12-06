## 1. Introduction

This document describes how to use the CORDS fault injection framework to analyze how distributed storage systems react to partial storage faults such as data corruption and I/O errors. Our paper can be found here: https://www.usenix.org/system/files/conference/fast17/fast17-ganesan.pdf

If you use this work in some way, please cite our paper. <a href="http://research.cs.wisc.edu/adsl/Publications/cords-fast17.bib"> Here</a> is the bibtex. 

CORDS is a simple file-system fault injection framework. It has two main components. 

1. errfs, a user-level FUSE file system that injects file-system faults into application-level on-disk data structures.    
1. errbench, a set of system-specific workloads.

## 2. Setup

We developed, tested, and ran all our experiments on Ubuntu 14.04 (kernel version: 4.2.0-38-generic). However, the setup should not be very different if you are using any other Linux kernel version or distro. 

### a. Installing FUSE lib
wget https://github.com/libfuse/libfuse/releases/download/fuse-2.9.7/fuse-2.9.7.tar.gz; tar -xvzf fuse-2.9.7.tar.gz;
cd fuse-2.9.7/; ./configure; make -j33; sudo make install

### b. gcc-5/g++-5
sudo apt-get install -y gcc-5 g++-5;
sudo update-alternatives;
sudo update-alternatives --remove-all gcc;
sudo update-alternatives --remove-all g++;
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-5 20;
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-5 20;
sudo update-alternatives --config gcc;
sudo update-alternatives --config g++;

### c. Application binaries
Cords intends to test different distributed storage systems. You need to install your target distributed storage system. For example, to if you want to test ZooKeeper-3.4.8, you need to:

wget http://www.webhostingreviewjam.com/mirror/apache/zookeeper/zookeeper-3.4.8/zookeeper-3.4.8.tar.gz; tar -xvzf zookeeper-3.4.8.tar.gz

Also, you need to build and install the ZooKeeper binaries (you will need JDK, JRE, and maven for this). Similarly, you need to build and install all its dependencies. 

## 3. Examining a distributed storage system

Scripts to examine a particular distributed storage system can be found inside the systems directory from the base of the repository. 
In this section, we will use the example of ZooKeeper (systems/zk directory contains the scripts for examining ZooKeeper). In this directory, you will find a script called zk_init.sh. This script simply initializes a three-node ZooKeeper that runs on the testing machine and inserts a single data item into the cluster. The script assumes that the ZooKeeper binaries and its dependencies are installed properly at some path on the file system. 

On top of such an initialized state, we can run a workload such as read/write. During this workload is when CORDS will inject different file-system faults such as data corruption and I/O errors. See our paper for the exact fault model used by CORDS. 

To know what blocks are accessed during a workload, we have simple tracing script. This tracing script configures errfs to run in the tracing mode and runs the supplied workload command and dumps the details of the blocks access by the workload into trace{i} files (where i is the node id of a server in the cluster). The below command shows how to collect the block access information for the zookeeper workload. 

trace.py --trace_files ./systems/zk/trace0 ./systems/zk/trace1 ./systems/zk/trace2 --data_dirs ./systems/zk/workload_dir0 ./systems/zk/workload_dir1/ ./systems/zk/workload_dir2/ --workload_command ./systems/zk/zk_workload_read.py --ignore_file ./systems/zk/ignore 

All parameters to the trace script are required except the ignore_file parameter. The ignore_file is a simple text file describing what files can be ignored with respect to block access information. Please the ignore file for ZooKeeper for more understanding (for ZooKeeper, it is just its log files and the pid files which are cosmetic files and do not contain user data or the cluster metadata).

Once the tracing information is available, you can check for how ZooKeeper reacts to different file-system faults by running the below command:

cords.py --trace_files ./systems/zk/trace0 ./systems/zk/trace1 ./systems/zk/trace2 --data_dirs ./systems/zk/workload_dir0 ./systems/zk/workload_dir1/ ./systems/zk/workload_dir2/ --workload_command ./systems/zk/zk_workload_read.py

This command will run the supplied workload several times, injecting a different fault each time. Results (how the cluster behaved, what the client observed) for each run (what fault was injected for what block on what file) are dumped into a directory. By default, this is /run/shm. This can be overriden by specifying the --cords_results_base_dir parameter to the cords script. Once the results are accumulated, we analyze them to categorize the local behavior of the node where the fault was injected and the global effect across the cluster. We repeat this process for all workloads for a given system and for multiple systems. Extracting behavioral information from the logs and outputs is system specific and very simple (involving simple greps, seds, and some simple python code). Please contact the authors if you are interested in how to do this for your target system. 

## 4. Contact Information

Aishwarya Ganesan (ag@cs.wisc.edu) and Ramnatthan Alagappan (ra@cs.wisc.edu) are the primary contacts for any questions related to the fault-injection framework and this work in general. 

The CORDS framework and the results are by-products of the distributed storage reliability research project (http://research.cs.wisc.edu/adsl/Publications/) at ADSL at the University of Wisconsin-Madison. Please <a href="http://research.cs.wisc.edu/adsl/Publications/cords-fast17.bib">cite this paper</a>, if you use this framework or results.  

If you want to use CORDS for your data store, or if you wish to get the workloads and testing results for a system that we have discussed in the paper, please drop us a mail at ag@cs.wisc.edu or ra@cs.wisc.edu.