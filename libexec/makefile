CC=gcc
CFLAGS=-c -DLZHUF
LDFLAGS=
SOURCES=$(wildcard *.c)
OBJECTS=$(SOURCES:.c=.o)
EXECUTABLE=lzhuf

all: $(SOURCES) $(EXECUTABLE)

$(EXECUTABLE): $(OBJECTS)
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

.cpp.o:
	$(CC) $(CFLAGS) $< -o $@

clean:
	$(RM) $(EXECUTABLE) *.o

install:
	cp $(EXECUTABLE) ../build
