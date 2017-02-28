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
	cout<<argv[1]<<endl;
	std::string filename = string(argv[1]) + "/foo";

	cout<<filename<<endl;
	fd = open(filename.c_str(), O_RDWR | O_CREAT , S_IRWXU);
	assert(fd > 0);
	assert(read(fd, buf, BS) == BS);
	cout<<"Read done!"<<endl;
	assert(write(fd, buf, BS) == BS);
	assert(write(fd, buf, BS) == BS);
	assert(fsync(fd) == 0);
	assert(close(fd) == 0);
}
