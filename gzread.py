import string
import zlib
import __builtin__

# implements a python function that reads and writes a gzipped file
# the user of the file doesn't have to worry about the compression,
# but random access is not allowed

# based on Andrew Kuchling's minigzip.py distributed with the zlib module

FTEXT, FHCRC, FEXTRA, FNAME, FCOMMENT = 1, 2, 4, 8, 16

def read32(buf):
    v = ord(buf[0])
    v = v + (ord(buf[1]) << 8)
    v = v + (ord(buf[2]) << 16)
    v = v + (ord(buf[3]) << 24)
    return v

def open(filename, fileobj=None):
    return GzipFile(filename, fileobj)

class GzipFile:

    myfileobj = None

    def __init__(self, filename=None, fileobj=None):
	if fileobj is None:
	    fileobj = self.myfileobj = __builtin__.open(filename, 'r')
	self._init_read()
	self.decompress = zlib.decompressobj(-zlib.MAX_WBITS)
	self.fileobj = fileobj
	self.compressed = 1
	self._read_gzip_header()

    def _init_read(self):
	self.crc = zlib.crc32("")
	self.size = 0
	self.extrabuf = ""
	self.extrasize = 0
	self.lastbuf = ""

    def _read_gzip_header(self):
	magic = self.fileobj.read(2)
	if magic != '\037\213':
	    self._unread(magic)
	    self.compressed = 0
	    return
	method = ord( self.fileobj.read(1) )
	if method != 8:
	    raise RuntimeError, 'Unknown compression method'
	flag = ord( self.fileobj.read(1) )
	# modtime = self.fileobj.read(4)
	# extraflag = self.fileobj.read(1)
	# os = self.fileobj.read(1)
	self.fileobj.read(6)

	if flag & FEXTRA:
	    # Read & discard the extra field, if present
	    xlen=ord(self.fileobj.read(1))	      
	    xlen=xlen+256*ord(self.fileobj.read(1))
	    self.fileobj.read(xlen)
	if flag & FNAME:
	    # Read and discard a null-terminated string containing the filename
	    while (1):
		s=self.fileobj.read(1)
		if not s or s=='\000': break
	if flag & FCOMMENT:
	    # Read and discard a null-terminated string containing a comment
	    while (1):
		s=self.fileobj.read(1)
		if not s or s=='\000': break
	if flag & FHCRC:
	    self.fileobj.read(2)     # Read & discard the 16-bit header CRC

    def read(self,size=None):
	if self.extrasize <= 0 and self.fileobj is None:
	    return ''

	if not self.compressed:
	    chunk = ''
	    if size and self.extrasize >= size:
		chunk = self.extrabuf[:size]
		self.extrabuf = self.extrabuf[size:]
		self.extrasize = self.extrasize - size
		return chunk
	    if self.extrasize:
		chunk = self.extrabuf
		if size:
		    size = size - self.extrasize
		self.extrasize = 0
		self.extrabuf = ''
	    if not size:
		return chunk + self.fileobj.read()
	    else:
		return chunk + self.fileobj.read(size)

	readsize = 1024
	if not size:	# get the whole thing
	    try:
		while 1:
		    self._read(readsize)
		    readsize = readsize * 2
	    except EOFError:
		size = self.extrasize
	else:	       # just get some more of it
	    try:
		while size > self.extrasize:
		    self._read(readsize)
		    readsize = readsize * 2
	    except EOFError:
		pass
	
	chunk = self.extrabuf[:size]
	self.extrabuf = self.extrabuf[size:]
	self.extrasize = self.extrasize - size

	return chunk

    def _unread(self, buf):
	self.extrabuf = buf + self.extrabuf
	self.extrasize = len(buf) + self.extrasize

    def _read(self, size=1024):
	try:
	    buf = self.fileobj.read(size)
	except AttributeError:
	    raise EOFError, "Reached EOF"
	if buf == "":
	    uncompress = self.decompress.flush()
	    if uncompress == "":
		self._read_eof()
		self.fileobj = None
		raise EOFError, 'Reached EOF'
	else:
	    xlen = len(buf)
	    if xlen >= 8:
		xoff = 0
		boff = xlen - 8
	    else:
		xoff = 8 - xlen
		boff = 0
	    self.lastbuf = self.lastbuf[:xoff] + buf[boff:]
	    uncompress = self.decompress.decompress(buf)
	self.crc = zlib.crc32(uncompress, self.crc)
	self.extrabuf = self.extrabuf + uncompress
	self.extrasize = self.extrasize + len(uncompress)
	self.size = self.size + len(uncompress)

    def _read_eof(self):
	crc32 = read32(self.lastbuf[:4])
	isize = read32(self.lastbuf[4:8])
	if crc32 != self.crc:
	    raise IOError, 'CRC check failed'
	elif isize != self.size:
	    raise IOError, 'Incorrect length of data produced'

    def close(self):
	self.fileobj = None
	if self.myfileobj:
	    self.myfileobj.close()
	    self.myfileobj = None

    def flush(self):
	self.fileobj.flush()

    def seek(self):
	raise IOError, 'Random access not allowed in gzip files'

    def tell(self):
	raise IOError, 'I won\'t tell() you for gzip files'

    def isatty(self):
	return 0

    def readline(self):
	bufs = []
	readsize = 100
	while 1:
	    c = self.read(readsize)
	    i = string.find(c, '\n')
	    if i >= 0 or c == '':
		bufs.append(c[:i])
		self._unread(c[i+1:])
		return string.join(bufs, '')
	    bufs.append(c)
	    readsize = readsize * 2

    def readlines(self):
	buf = self.read()
	return string.split(buf, '\n')
