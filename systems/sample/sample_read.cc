#include <string>
#include <iostream>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <assert.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>

using namespace std;

#define BS 4096
int main(int argc, char** argv)
{
	int fd = -1;
	char* buf;
	buf = (char*)malloc(BS);
	memset(buf, 97, BS);
	std::string filename = string(argv[1]) + "/foo";
	fd = open(filename.c_str(), O_RDONLY, S_IRWXU);
	assert(fd > 0);
	int ret = pread(fd, buf, 1, 51);
	cout<<"Ret from client"<<ret<<endl;
	assert(ret == 1);
	assert(close(fd) == 0);
}
