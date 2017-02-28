all:
	g++ errfs.cc util.cc -o errfs `pkg-config fuse --cflags --libs` -std=c++11
clean :
	rm -f errfs; rm -f *.o