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

#include <vector>
#include <map>

#define BLOCKSIZE 4096
#define SECTOR_SIZE 512
#define SECTORS_PER_BLOCK (BLOCKSIZE/SECTOR_SIZE)

// fault config
enum fault_mode { err_eio = 42 , err_enospc /*43*/, err_edquot /*44*/,
                  corr_zero /*45*/, corr_garbage /*46*/, corr_similar /*47*/,
                  no_op /*48*/};

typedef std::string filepath;
typedef std::vector<std::string> filenames;
typedef std::vector<bool> injected;
typedef fault_mode err_type; 

union corrinfo 
{
    struct bitcorrinfo 
	{
       int offset;
       int length;
    } mbitcorrinfo;

    int blocknr;
};

typedef union corrinfo mcorrinfo;

typedef std::tuple<filenames, mcorrinfo, err_type, injected> fault_config;

// fault spec
typedef int index_into_buf;
typedef int len_bytes;
typedef std::tuple<err_type, index_into_buf, len_bytes> fault_spec;

class util 
{
    public:
        static bool should_err(fault_config& cfg, fault_spec& spec, 
             const std::string filename, int offset, int size, const std::string op);
        static char* random_bytes(int num_bytes);
        static char* random_bit_flip(char* buffer, int length);
        static int block_roundup(int x);
        static int block_rounddown(int x);
        static err_type err_type_for_string(std::string str);
        static std::tuple<bool, int> is_err_file(
            std::vector<std::string> err_filenames, std::string file_in_question);
    private:
        static std::map<err_type, bool> err_processed_map;

        static std::vector<std::string>& split(const std::string &s, char delim,
             std::vector<std::string> &elems);
        static std::vector<std::string> split(const std::string &s, char delim);
        static bool is_present(std::vector<int> v, int value);
        static bool is_block_append(std::string filename, int block_nr);
};