#include <string>
#include <iostream>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <assert.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>

#define BS 4096
using namespace std;

int main(int argc, char** argv)
{
	int fd = -1, ret = -1;
	char* buf = (char*) malloc(BS * sizeof(char));
	memset(buf, 'a', BS);

	string filename1 = string(argv[1]) + "/foo";
	string filename2 = string(argv[1]) + "/bar";

	cout<<"File1:"<<filename1;
	cout<<"File2:"<<filename2;
	fd = open(filename1.c_str(), O_RDWR, S_IRWXU);

	assert(fd > 0);
	write(fd, buf, BS); // Just ignore any errors
	assert(close(fd) == 0);

	assert(rename(filename1.c_str(), filename2.c_str()) == 0);
	memset(buf, 'b', BS);
	fd = open(filename2.c_str(), O_RDWR, S_IRWXU);
	assert(fd > 0);
	assert(write(fd, buf, BS) == BS);
	assert(close(fd) == 0);	
	return 0;
}
