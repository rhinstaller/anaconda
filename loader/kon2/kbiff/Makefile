CFLAGS=-O3 -g
OBJS=	kbiff.o

kbiff:	$(OBJS)
	$(CC) -o $@ $< -lncurses

install:
	install -cs kbiff /usr/bin

clean:
	rm -f $(OBJS) kbiff
