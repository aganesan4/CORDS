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

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string>
#include <map>
#include <vector>
#include <iostream>
#include <algorithm>
#include <sstream>
#include <fstream>
#include <cmath>
#include <assert.h>
#include <sys/mman.h>
#include <sys/statvfs.h>
#include <stdlib.h>
#include <dirent.h>
#include <assert.h>
#include <time.h>

#include "util.h"

using namespace std;

map<err_type, bool> util::err_processed_map = {{err_enospc, false}, 
                                                {err_edquot, false}};

bool util::is_block_append(std::string filename, int block_nr)
{
    struct stat* buf_before = (struct stat*)malloc(sizeof(struct stat));
    assert(stat(filename.c_str(), buf_before) == 0);
    // stat returns sectors
    int blocks_before = floor(buf_before->st_blocks / SECTORS_PER_BLOCK); 
    return (block_nr >= blocks_before);
}

err_type util::err_type_for_string(std::string str)
{
    if(str == "eio")
        return err_eio;
    else if(str == "cz")
        return corr_zero;
    else if(str == "cg")
        return corr_garbage;
    else if(str == "b")
        return corr_similar;
    else if(str == "esp")
        return err_enospc;
    else if(str == "edq")
        return err_edquot;
    else
        assert(false);
}

char* util::random_bytes(int num_bytes)
{
    assert(num_bytes <= BLOCKSIZE);
    srand ((unsigned int) time (NULL));
    char* rand_bytes = (char*) malloc (num_bytes);
    for (int i = 0; i < num_bytes; i++)
        rand_bytes[i] = rand()%128;

    return rand_bytes;
}

char* util::random_bit_flip(char* buffer, int length)
{
    srand ((unsigned int) time (NULL));
    int no_bits = length * 8;
    int position = rand() % no_bits;
    int byte_pos = position / 8;
    int bit_pos = position % 8;
    char temp = 0x01;
    temp = temp << bit_pos;  
    char corr = buffer[byte_pos] ^ temp;
    buffer[byte_pos] = corr;
    return buffer;
}

int util::block_roundup(int x)
{
    return ceil(x * 1.0 / BLOCKSIZE) * BLOCKSIZE;
}

int util::block_rounddown(int x)
{
    return floor(x * 1.0 / BLOCKSIZE) * BLOCKSIZE;
}

bool util::is_present(vector<int> v, int value)
{
    return (find(v.begin(), v.end(), value) !=v.end());
}

vector<string>& 
util::split(const string &s, char delim, vector<string> &elems)
{
    stringstream ss(s);
    string item;
    while (getline(ss, item, delim)) 
        elems.push_back(item);

    return elems;
}

vector<string>
util::split(const string &s, char delim) 
{
    vector<string> elems;
    split(s, delim, elems);
    return elems;
}

tuple<bool, int> 
util::is_err_file(std::vector<std::string> err_filenames, 
    std::string file_in_question)
{
    for(int i=0; i < err_filenames.size(); i++)
    {
        if(file_in_question == err_filenames[i])
            return make_tuple(true, i);
    }

    return make_tuple(false, -1);
}

bool 
util::should_err(fault_config &cfg, fault_spec &spec, const string filename,
    int offset, int size, const string op)
{
    int start_offset = offset; 
    int end_offset = start_offset + size;

    int total_blocks_touched = (block_roundup(end_offset) -
     block_rounddown(start_offset)) / BLOCKSIZE;
    assert(total_blocks_touched >= 1);
    int start_block_nr = (int) floor(start_offset / BLOCKSIZE);
    err_type err_mode = get<2>(cfg);

    if(op == "write")
    {
        tuple<bool, int> res = is_err_file(get<0>(cfg), filename);
        if(get<0>(res)) 
        {
            assert(get<1>(res) >= 0);
            if(err_mode == err_eio)
            {
                for(int i = start_block_nr; i < start_block_nr + total_blocks_touched; i++)
                {
                    if(i == get<1>(cfg).blocknr)
                    {
                        spec = make_tuple(get<2>(cfg), -1, -1);
                        return true;
                    }
                }
            }
            else if(err_mode == err_enospc or err_mode == err_edquot)
            {
                for(int i = start_block_nr; i < start_block_nr + total_blocks_touched; i++)
                {
                    if(i == get<1>(cfg).blocknr and is_block_append(filename, i) and
                        err_processed_map[err_mode] == false)
                    {
                        spec = make_tuple(err_mode, -1, -1);
                        err_processed_map[err_mode] = true;
                        return true;
                    }
                    else
                    {
                        if(is_block_append(filename, i) and
                            err_processed_map[err_mode] == true)
                        {
                            spec = make_tuple(err_mode, -1, -1);
                            return true;
                        }
                    }
                    
                }   
            }
        }    
        
        spec = make_tuple(no_op, -1, -1);
        return false;
    }
    else if(op == "read")
    {
        // For reads we need to consider both corruptions and io errors
        // we treat corruptions and errors uniformly
        tuple<bool, int> res = is_err_file(get<0>(cfg), filename);
        if(get<0>(res)) 
        {
            assert(get<1>(res) >= 0);
            if(err_mode == err_eio)
            {            
                for(int i = start_block_nr; i < start_block_nr + total_blocks_touched; i++)
                {
                    if(i == get<1>(cfg).blocknr)
                    {
                        // stupid - but for debugging.
                        assert(err_mode == err_eio); 
                        spec = make_tuple(err_mode, -1, -1);
                        return true;
                    }
                    else
                        continue;
                }

                spec = make_tuple(no_op, -1, -1);
                return false;
            }
            else if(err_mode == corr_zero or err_mode == corr_garbage)
            {
                map<int, tuple<int, int>> block_bytes_map;
                int index = 0;
                int remaining = size;
                int first_block_bytes;

                int frag_size = block_roundup(start_offset) - start_offset;
                assert(frag_size >= 0 and frag_size <= BLOCKSIZE);

                if(frag_size == 0) // block aligned
                    first_block_bytes = (size < BLOCKSIZE)? size:BLOCKSIZE;
                else // unaligned
                    first_block_bytes = (size < frag_size)? size:frag_size;

                block_bytes_map[start_block_nr] = make_tuple(index, first_block_bytes);
                index += first_block_bytes;
                remaining = size - first_block_bytes;
                
                for(int i = start_block_nr + 1; i < start_block_nr + total_blocks_touched; i++)
                {
                    if(remaining >= BLOCKSIZE)
                    {
                        block_bytes_map[i] = make_tuple(index, BLOCKSIZE);
                        remaining -= BLOCKSIZE;
                        index += BLOCKSIZE;
                    }
                    else
                    {
                        assert(i ==  start_block_nr + total_blocks_touched - 1);
                        block_bytes_map[i] = make_tuple(index, remaining);
                        remaining -= get<1>(block_bytes_map[i]);
                        index += get<1>(block_bytes_map[i]);
                    }
                }   
                assert(remaining == 0);

                for (auto const& x : block_bytes_map)
                {
                    int block_in_question = x.first;
                    if(block_in_question == get<1>(cfg).blocknr)
                    {
                        int buf_index = get<0>(x.second);
                        int len = get<1>(x.second);
                        assert(err_mode == corr_zero or err_mode == corr_garbage); 
                        spec = make_tuple(err_mode, buf_index, len);
                        return true;
                    }
                    else
                        continue;
                }

                spec = make_tuple(no_op, -1, -1);
                return false;
            }
            else if(err_mode == corr_similar)
            {
                int bc_start_offset = get<1>(cfg).mbitcorrinfo.offset;
                int bc_end_offset = bc_start_offset + get<1>(cfg).mbitcorrinfo.length;

                std::tuple<int, int> intersection = 
                    make_tuple(std::max(bc_start_offset, start_offset),
                    std::min(bc_end_offset, end_offset));
                    
                if (get<1>(intersection) < get<0>(intersection)) 
                {
                    spec = make_tuple(no_op, -1, -1);
                    return false;
                }
                else
                {
                    int buf_index = get<0>(intersection) - start_offset;
                    int len = get<1>(intersection) - get<0>(intersection);
                    assert(err_mode == corr_similar); 
                    spec = make_tuple(err_mode, buf_index, len);
                    return true;
                }
            }
            else // errmode that we do not care for reads
            {
                spec = make_tuple(no_op, -1, -1);
                return false;   
            }
        }
        else // filenames do not match
        {
            spec = make_tuple(no_op, -1, -1);
            return false;
        }
    }
    else // some other operation than read and write
        assert(false); 
}