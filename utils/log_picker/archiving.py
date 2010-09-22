import os
import tempfile
import tarfile
import bz2


class ArchivationError(Exception):
    pass

class NoFilesArchivationError(ArchivationError):
    pass

class ArchiveBaseClass(object):
    """Base class for archive classes."""

    _compression = False
    _ext = ".ext"
    _mimetype = ""
    
    def __init__(self, *args, **kwargs):
        self._tar_ext = ".tar"
    
    @property
    def support_compression(self):
        """Return True if compression is supported/used."""
        return self._compression
        
    @property
    def file_ext(self):
        """Return extension for output file."""
        return self._ext
       
    @property 
    def mimetype(self):
        """Return archive mime type."""
        return self._mimetype
    
    def _create_tmp_tar(self, filelist):
        _, tmpfile = tempfile.mkstemp(suffix=self._tar_ext)
        tar = tarfile.open(tmpfile, "w")
        for name in filelist:
            pieces = name.rsplit('/', 2)
            arcname = "%s/%s" % (pieces[-2], pieces[-1])
            tar.add(name, arcname=arcname)
        tar.close()
        return tmpfile
       
    def create_archive(self, outfilename, filelist):
        raise NotImplementedError()


class Bzip2Archive(ArchiveBaseClass):
    """Class for bzip2 compression."""
    
    _compression = True
    _ext = ".bz2"
    _mimetype = "application/x-bzip2"
    
    def __init__(self, usetar=True, *args, **kwargs):
        ArchiveBaseClass.__init__(self, args, kwargs)
        self.usetar = usetar

    @property
    def file_ext(self):
        """Return extension for output file."""
        if self.usetar:
            return "%s%s" % (self._tar_ext, self._ext)
        return self._ext

    def create_archive(self, outfilename, filelist):
        """Create compressed archive containing files listed in filelist."""
        if not filelist:
            raise NoFilesArchivationError("No files to archive.")
        
        size = 0
        for file in filelist:
            size += os.path.getsize(file)
        if size <= 0:
            raise NoFilesArchivationError("No files to archive.")
            
        if not self.usetar and len(filelist) > 1:
            raise ArchivationError( \
                            "Bzip2 cannot archive multiple files without tar.")
        
        if self.usetar:
            f_in_path = self._create_tmp_tar(filelist)
        else:
            f_in_path = filelist[0]
         
        f_in = open(f_in_path, 'rb')
        f_out = bz2.BZ2File(outfilename, 'w')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        
        if self.usetar:
            os.remove(f_in_path)
        
        return outfilename

