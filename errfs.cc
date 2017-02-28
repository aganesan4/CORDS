// Copyright (c) 2016 Aishwarya Ganesan and Ramnatthan Alagappan.
// All Rights Reserved.
// 
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include <map>
#include <string>
#include <iostream>
#include <cmath>
#include <algorithm>

#include "util.h"

using namespace std;

string mode;
string dump_file;
fault_config f_cfg;

extern "C" {

#define FUSE_USE_VERSION  26
#include <fuse.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <dirent.h>
#include <sys/xattr.h>
#include <assert.h>

static int errfs_getattr(const char* path, struct stat* buf) 
{
    int ret = 0;
    ret = stat(path, buf);
    if (ret < 0) 
        return -errno;

    return 0;    
}

static int errfs_readdir(const char* path, void* buf, fuse_fill_dir_t filler,
                            off_t offset, struct fuse_file_info* fi)
{
    int ret = 0;   
    DIR *dp = (DIR *) fi->fh;
    struct dirent *de;

    while ((de = readdir(dp)) != NULL) 
    {
        struct stat st;
        memset(&st, 0, sizeof(st));
        st.st_ino = de->d_ino;
        st.st_mode = de->d_type << 12;
        if (filler(buf, de->d_name, &st, 0))
            break;
    }
    return 0;    
}

static int errfs_open(const char* path, struct fuse_file_info* fi) 
{
    int ret = 0;
    ret = open(path, fi->flags);
    if (ret < 0) 
        return -errno;

    fi->fh = ret;
    return 0;
}

static int dump_entry(string filename, string op, int offset, int size)
{
    FILE* dump;
    dump = fopen(dump_file.c_str(),"a+");
    assert(dump);
    fprintf(dump, "%s\t%s\t%d\t%d\n", filename.c_str(), op.c_str(), offset, size);
    fclose(dump);
    return 0;
}

static int dump_dirop_entry(string op, string src, string dest)
{
    FILE* dump;
    dump = fopen(dump_file.c_str(),"a+");
    assert(dump);
    fprintf(dump, "%s\t%s\t%s\n", op.c_str(), src.c_str(), dest.c_str());
    fclose(dump);
    return 0;
}

static int errfs_read(const char* path, char* buf, size_t size, off_t offset,
                        struct fuse_file_info* fi) 
{
    int ret = 0;
    if(mode == "err")
    {
        fault_spec spec;
        volatile bool should_err = util::should_err(f_cfg, spec, path, offset, size, "read");
        volatile err_type type = get<0>(spec);
        int buf_index = get<1>(spec);
        int len = get<2>(spec);

        // Perform the original read
        ret = pread(fi->fh, buf, size, offset);
        // read can return smaller than requested
        assert(ret <= size); 

        if(should_err)
        {
            int se_fd;
            se_fd = open("/tmp/shoulderr", O_CREAT | O_RDWR);
            assert(se_fd >  0);
            assert(write(se_fd, "true", 4) == 4);
            assert(close(se_fd) == 0);

            tuple<bool, int> res = util::is_err_file(get<0>(f_cfg), path);
            int filename_index = get<1>(res);
            assert(get<0>(res));
            assert(filename_index >= 0);
            get<3>(f_cfg)[filename_index] = true;
        
        	// for reads we should not see enospc and edquot
            assert(type == err_eio or type == corr_zero or type == corr_garbage or type == corr_similar);
            if(type == err_eio)
            {
                assert(buf_index == -1 and len == -1);
                errno = EIO;
                ret = -errno;
            }
            else if(type == corr_zero or type == corr_garbage)
            {
		        assert(len <= BLOCKSIZE);
                assert(buf_index >= 0 and buf_index < size);
                assert(buf_index + len <= size); 

                //Check if we are going to corrupt only in the returned portion of data
                if(buf_index <= ret)
                {             
                    int to_corrupt_len = (buf_index + len <= ret ? len : ret - buf_index) ; 
                    assert(to_corrupt_len >= 0 and to_corrupt_len <= len);

                    if(type == corr_zero) // replace with zeros
                        memset(buf + buf_index, 0, to_corrupt_len);    
                    else if(type == corr_garbage) // replace with garbage
                        memcpy(buf + buf_index, util::random_bytes(to_corrupt_len), to_corrupt_len);    
		        }
                //else to-corrupt portion is outside of the result
            }
            else if(type == corr_similar)
            {
                assert(buf_index >= 0 and buf_index < size);
                assert(buf_index + len <= size); 
                if(buf_index <= ret)
                {             
                    int to_corrupt_len = (buf_index + len <= ret ? len : ret - buf_index) ; 
                    assert(to_corrupt_len >= 0 and to_corrupt_len <= len);
                    char* corr_bytes = (char*) malloc (to_corrupt_len);
                    memcpy(corr_bytes, buf + buf_index, to_corrupt_len);   
                    memcpy(buf + buf_index, util::random_bit_flip(corr_bytes, to_corrupt_len), to_corrupt_len);    
                }
            }
        }
        else 
            assert(type == no_op and buf_index == -1 and len == -1); 
        
        return ret;
    }
    else if(mode == "trace")
    {
        // Just pass the error as-is to the application.
        ret = pread(fi->fh, buf, size, offset);
        if(ret == -1)
            ret = -errno;
        
        dump_entry(path, "r", offset, size);
        return ret;
    }
}

int errfs_write(const char* path, const char* buf, size_t size, off_t offset,
                struct fuse_file_info* fi) 
{
    int ret = 0;
    if(mode == "err")
    {
        fault_spec spec;
        bool should_err = util::should_err(f_cfg, spec, path, offset, size, "write");
        err_type type = get<0>(spec);
        int buf_index = get<1>(spec);
        int len = get<2>(spec);

        if(should_err)
        {
            // no corruption for writes
            assert(type == err_eio or type == err_enospc or type == err_edquot); 
            assert(buf_index == -1 and len == -1);

            int se_fd;
            se_fd = open("/tmp/shoulderr", O_CREAT | O_RDWR);
            assert(se_fd >  0);
            assert(write(se_fd, "true", 4) == 4);
            assert(close(se_fd) == 0);

            tuple<bool, int> res = util::is_err_file(get<0>(f_cfg), path);
            int filename_index = get<1>(res);
            assert(get<0>(res));
            assert(filename_index >= 0);
            get<3>(f_cfg)[filename_index] = true;

            if(type == err_eio)
	            errno = EIO;
        	else if(type == err_enospc)
	            errno = ENOSPC;
        	else if(type == err_edquot)
	            errno = EDQUOT;
	        
        	ret = -errno;
        }
        else
        {
            assert(type == no_op and buf_index == -1 and len == -1); 
            ret = pwrite(fi->fh, buf, size, offset);
            // if we did not cause any problems, then just assert everything is fine.
            // although ret may be lesser than size, we have never encountered that case
            // in practice. if hit, can be changed to lesser or equal.
            assert(ret == size); 
        }
        
        return ret;
    }
    else if(mode == "trace")
    {
    	struct stat* buf_before = (struct stat*)malloc(sizeof(struct stat));
		assert(stat(path, buf_before) == 0);
		int blocks_before = floor(buf_before->st_blocks / SECTORS_PER_BLOCK);

        ret = pwrite(fi->fh, buf, size, offset);

		int remaining = ret;
		int start_offset = offset; 
	    int end_offset = start_offset + ret;
	    int total_blocks_touched = 
            (util::block_roundup(end_offset) - util::block_rounddown(start_offset)) / BLOCKSIZE;
	    assert(total_blocks_touched >= 1);
	    int start_block_nr = (int) floor(start_offset / BLOCKSIZE);
		int frag_size = util::block_roundup(offset) - offset;
		assert(frag_size >= 0 and frag_size <= BLOCKSIZE);
		int first_block_bytes;
		string write_mode = "w";		
		
		if(frag_size == 0)// block aligned
			first_block_bytes = (size < BLOCKSIZE)? size:BLOCKSIZE;
		else // unaligned
			first_block_bytes = (size < frag_size)? size:frag_size;

        if(start_block_nr >= blocks_before)
			write_mode = "a"; // appending
	
		dump_entry(path, write_mode, start_offset, first_block_bytes);		
		
		remaining -= first_block_bytes;
		start_offset += first_block_bytes;

		for(int i = start_block_nr + 1; i < start_block_nr + total_blocks_touched; i++)
        {
            if(i >= blocks_before)
                write_mode = "a";
                
            if(remaining >= BLOCKSIZE)
            {
                dump_entry(path, write_mode, start_offset, BLOCKSIZE);		
               	remaining -= BLOCKSIZE;
               	start_offset += BLOCKSIZE;
            }
            else
            {
                assert(i ==  start_block_nr + total_blocks_touched - 1);
                dump_entry(path, write_mode, start_offset, remaining);		
               	remaining -= remaining;
               	start_offset += remaining;
            }
        }   
        assert(remaining == 0);
        assert(start_offset == end_offset);

        return ret;
    }
}

int errfs_unlink(const char *path) 
{
    int ret = 0;
	ret = unlink(path); 

    if(mode == "trace")
    	dump_dirop_entry("unlink", path, "");
    else if(mode == "err")
    {
        // ignore fuse hidden files
		if(ret == 0 && strstr(path ,".fuse_hidden") == NULL)
		{
			tuple<bool, int> res = util::is_err_file(get<0>(f_cfg), path);
			if(get<0>(res))
			{
				int filename_index = get<1>(res);
                bool fault_already_injected = get<3>(f_cfg)[filename_index];
                bool space_fault = (get<2>(f_cfg) == err_enospc or get<2>(f_cfg) == err_edquot);
                if(fault_already_injected)
                {
                	if(!space_fault)
                	{
	                    get<0>(f_cfg).erase(get<0>(f_cfg).begin() + filename_index);
	                    get<3>(f_cfg).erase(get<3>(f_cfg).begin() + filename_index);
                	}
                }
			}

		}
	}

    if (ret < 0) 
        return -errno;

    return 0;
}

int errfs_create(const char* path, mode_t mode, struct fuse_file_info* fi) 
{  
    int fd;
    fd = open(path, fi->flags, mode);
    if (fd == -1)
        return -errno;
    fi->fh = fd;
    return 0;    
}

int errfs_fgetattr(const char* path, struct stat* buf, struct fuse_file_info* fi) 
{  
    int ret = 0;
    ret = fstat((int) fi->fh, buf);
    if (ret < 0)
        return -errno;

    return 0;    
}

int errfs_opendir(const char* path, struct fuse_file_info* fi) 
{  
    int ret = 0;    
    DIR* dir = opendir(path);

    if (!dir) 
        return -errno;
    
    fi->fh = (int64_t) dir;
    return 0;    
}

int errfs_access(const char* path, int mode)
{  
    int ret = 0;
    ret = access(path, mode); 
    if (ret < 0)
        return -errno;

    return 0;    
}

int errfs_truncate(const char* path, off_t length) 
{  
    int ret = 0;
    ret = truncate(path, length); 
    if (ret < 0)
        return -errno;

    return 0;
}

int errfs_mknod(const char *path, mode_t mode, dev_t dev)
{
    int ret = 0;
    ret = mknod(path, mode, dev);    
    if (ret < 0) 
        return -errno;
    
    return 0;
}

int errfs_mkdir(const char *path, mode_t mode)
{
    int ret = 0;
    ret = mkdir(path, mode);
    if (ret < 0)
        return -errno;

    return 0;
}

int errfs_rmdir(const char *path)
{
    int ret = 0;
    ret = rmdir(path); 
    if (ret < 0) 
        return -errno;

    return 0;
}

int errfs_symlink(const char *target, const char *linkpath)
{
	assert(false); // Don't handle symlink for now. TODO: Fix this if apps want.
    int ret = 0;
    
    ret = symlink(target, linkpath);
    if (ret < 0)
        return -errno;
    
    return 0;
}

int errfs_rename(const char *oldpath, const char *newpath)
{
    int ret = rename(oldpath, newpath);
	if(mode == "trace")
		dump_dirop_entry("rename", oldpath, newpath);
	else if(mode == "err")
	{
        // ignore fuse hidden files
		if(ret == 0 && strstr(oldpath ,".fuse_hidden") == NULL && strstr(newpath ,".fuse_hidden") == NULL)
		{
		    tuple<bool, int> res = util::is_err_file(get<0>(f_cfg), newpath);
		    if(get<0>(res))
			{
				int filename_index = get<1>(res);
                bool fault_already_injected = get<3>(f_cfg)[filename_index];
                bool space_fault = (get<2>(f_cfg) == err_enospc or get<2>(f_cfg) == err_edquot);
                if(fault_already_injected)
                {
                	if(!space_fault)
                	{
	                    get<0>(f_cfg).erase(get<0>(f_cfg).begin() + filename_index);
	                    get<3>(f_cfg).erase(get<3>(f_cfg).begin() + filename_index);
               		}
                }
			}

			res = util::is_err_file(get<0>(f_cfg), oldpath);
			if(get<0>(res))
			{
			    int filename_index = get<1>(res);
			    assert(filename_index >= 0);
			    get<0>(f_cfg)[filename_index] = newpath;
			}
		}
	}
           
    if (ret < 0) 
        return -errno;

    return 0;
}

int errfs_link(const char *oldpath, const char *newpath)
{
    int ret = 0;
    ret = link(oldpath, newpath);

    if(mode == "trace")
    	dump_dirop_entry("link", oldpath, newpath);
    else if(mode == "err")
    {
		if(ret == 0 && strstr(oldpath ,".fuse_hidden") == NULL && strstr(newpath ,".fuse_hidden") == NULL)
		{
			tuple<bool, int> res = util::is_err_file(get<0>(f_cfg), oldpath);
			if(get<0>(res))
			{
			    int filename_index = get<1>(res);
			    assert(filename_index >= 0);
			    get<0>(f_cfg).push_back(newpath);
			}
		}
	}
    
    if (ret < 0)
        return -errno;

    return 0;
}

int errfs_chmod(const char *path, mode_t mode)
{
    int ret = chmod(path, mode);
    if (ret < 0)
        return -errno;

    return 0;
}

int errfs_chown(const char *path, uid_t owner, gid_t group)
{
    int ret = chown(path, owner, group);
    if (ret < 0) 
        return -errno;

    return 0;
}

int errfs_utime(const char *, struct utimbuf *) 
{ 
    cout << "errfs_utime not implemented" << endl;
    return -EINVAL;
}

int errfs_utimens(const char *path, const struct timespec tv[2])
{
    int res;
    res = utimensat(0, path, tv, AT_SYMLINK_NOFOLLOW);
    if (res == -1)
           return -errno;

    return 0;   
}

int errfs_bmap(const char *path, size_t blocksize, uint64_t *idx)
{
    cout << "errfs_bmap: not implemented." << endl;
    return 0;    
}

int errfs_setxattr(const char *path, const char *name,
                     const char *value, size_t size, int flags)
{
    int ret = setxattr(path, name, value, size, flags);
    if (ret < 0) 
        return -errno;

    return 0;
}

int errfs_statfs(const char *path, struct statvfs *stbuf)
{
    int res;
    res = statvfs(path, stbuf);
    if (res == -1)
        return -errno;
    return 0;
}

int errfs_getxattr(const char *path, const char *name, char *value, size_t size)
{
    int res = lgetxattr(path, name, value, size);
    if (res == -1)
        return -errno;
    return res;
}

int errfs_readlink(const char *path, char *buf, size_t size)
{
    int res;
    res = readlink(path, buf, size - 1);
    if (res == -1)
        return -errno;
    buf[res] = '\0';
    return 0;
}

int errfs_listxattr(const char *path, char *list, size_t size)
{
    int res = llistxattr(path, list, size);
    if (res == -1)
        return -errno;
    return res;
}

int errfs_removexattr(const char *path, const char *name)
{
    int res = lremovexattr(path, name);
    if (res == -1)
        return -errno;
    return 0;
}

static struct fuse_operations errfs_oper;
int main(int argc, char** argv) 
{
    errfs_oper.readlink = errfs_readlink;
    errfs_oper.statfs = errfs_statfs;
    errfs_oper.getattr  = errfs_getattr;
    errfs_oper.getxattr = errfs_getxattr,
    errfs_oper.listxattr = errfs_listxattr,
    errfs_oper.removexattr = errfs_removexattr,
    errfs_oper.readdir  = errfs_readdir;
    errfs_oper.open     = errfs_open;
    errfs_oper.read     = errfs_read;
    errfs_oper.mknod    = errfs_mknod;
    errfs_oper.write    = errfs_write;
    errfs_oper.unlink   = errfs_unlink;
    errfs_oper.setxattr = errfs_setxattr;
    errfs_oper.mkdir = errfs_mkdir;
    errfs_oper.rmdir = errfs_rmdir;
    errfs_oper.symlink = errfs_symlink;
    errfs_oper.rename = errfs_rename;
    errfs_oper.link = errfs_link;
    errfs_oper.chmod = errfs_chmod;
    errfs_oper.chown = errfs_chown;
    errfs_oper.truncate = errfs_truncate;
    errfs_oper.utime = errfs_utime;
    errfs_oper.opendir = errfs_opendir;
    errfs_oper.access = errfs_access;
    errfs_oper.create = errfs_create;
    errfs_oper.fgetattr = errfs_fgetattr;
    errfs_oper.utimens = errfs_utimens;
    errfs_oper.bmap = errfs_bmap;

    assert(argc >= 6);
    mode = argv[4];
    assert(mode == "trace" or mode == "err");

    if(mode == "trace")
    {
        cout<<"Tracing started..."<<endl;
        assert(argc == 6);
        dump_file = argv[5];
    }
    else if(mode == "err")
    {
        assert(argc == 8 or argc == 9);
        assert(string(argv[7]) == "eio" or string(argv[7]) == "cz" or
             string(argv[7]) == "cg" or string(argv[7]) == "b" or  
        	string(argv[7]) == "esp" or string(argv[7]) == "edq");

        if (string(argv[7]) == "eio" or string(argv[7]) == "cz" or
         string(argv[7]) == "cg" or string(argv[7]) == "esp" or
        string(argv[7]) == "edq")
        {
            assert(argc == 8);
            mcorrinfo blkcorr;
            blkcorr.blocknr = atoi(argv[6]);
            vector<string> fnames;
            vector<bool> injected_status;
            injected_status.push_back(false);
            fnames.push_back(argv[5]);
            f_cfg = make_tuple(fnames, blkcorr, 
                util::err_type_for_string(string(argv[7])), injected_status);
        }
        else
        {
            assert(argc == 9);
            mcorrinfo bitcorr;
            bitcorr.mbitcorrinfo.offset = atoi(argv[6]);
            bitcorr.mbitcorrinfo.length = atoi(argv[8]);
            vector<string> fnames;
            vector<bool> injected_status;
            injected_status.push_back(false);
            fnames.push_back(argv[5]);
            f_cfg = make_tuple(fnames, bitcorr,
             util::err_type_for_string(string(argv[7])), injected_status);
        }
    }

    argc = 4; // alter argc for fuselib
    return fuse_main(argc, argv, &errfs_oper, NULL);
}

} // extern C