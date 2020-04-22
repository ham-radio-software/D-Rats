CC=gcc
RM=rm
CFLAGS=-c -DLZHUF
LDFLAGS=
SOURCES=lzhuf.c main.c
OBJECTS=$(SOURCES:.c=.o)
EXECUTABLE=lzhuf

all: $(SOURCES) $(EXECUTABLE)

$(EXECUTABLE): $(OBJECTS)
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

.c.o:
	$(CC) $(CFLAGS) $< -o $@

clean:
	$(RM) $(EXECUTABLE) *.o
