import os
import stat
import shlex
import time
import subprocess


class LogMinerError(Exception):
    pass


class LogMinerBaseClass(object):
    """Base class for LogMiner classes. 
    LogMiner object represents one file/command/function 
    to get useful information (log)."""
        
    _name = "name"
    _description = "Description"
    _filename = "filename"
    _prefer_separate_file = True
    
    def __init__(self, logfile=None, *args, **kwargs):
        """@logfile open file object. This open file object will be used for 
        output generated during getlog() call."""
        self.logfile = logfile
        self._used = False
    
    @classmethod
    def get_filename(cls):
        """Suggested log filename."""
        return cls._filename
        
    @classmethod
    def get_description(cls):
        """Log description."""
        return cls._description
    
    def set_logfile(self, logfile):
        self.logfile = logfile
    
    def _write_separator(self):
        self.logfile.write('\n\n')
       
    def _write_files(self, files):
        if not isinstance(files, list):
            files = [files]

        if self._used:
            self._write_separator()
        self._used = True
        
        for filename in files:
            self.logfile.write('%s:\n' % filename)
            try:
                with open(filename, 'r') as f: 
                    self.logfile.writelines(f)
                    self.logfile.write('\n')
            except (IOError) as e:
                self.logfile.write("Exception while opening: %s\n" % e)
                continue
    
    def _run_command(self, command):
        if self._used:
            self._write_separator()
        self._used = True
        
        if isinstance(command, basestring):
            command = shlex.split(command)
        
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        self.logfile.write('STDOUT:\n%s\n' % out)
        self.logfile.write('STDERR:\n%s\n' % err)
        self.logfile.write('RETURN CODE: %s\n' % proc.returncode)
    
    def getlog(self):
        """Create log and write it to a file object 
        recieved in the constructor."""
        self._action()
        self._write_separator()
    
    def _action(self):
        raise NotImplementedError()



class AnacondaLogMiner(LogMinerBaseClass):
    """Class represents way to get Anaconda dump."""
    
    _name = "anaconda_log"
    _description = "Log dumped from Anaconda."
    _filename = "anaconda-dump"
    _prefer_separate_file = True

    def _action(self):
        # Actual state of /tmp
        old_state = set(os.listdir('/tmp'))
        
        # Tell Anaconda to dump itself
        try:
            anaconda_pid = open('/var/run/anaconda.pid').read().strip()
        except (IOError):
            raise LogMinerError("Anaconda pid file doesn't exists")
        
        proc = subprocess.Popen(shlex.split("kill -s USR2 %s" % anaconda_pid), 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.communicate()
        if proc.returncode:
            raise LogMinerError('Error while sending signal to Anaconda')
        
        time.sleep(5)
        
        # Check if new traceback file exists
        new_state = set(os.listdir('/tmp'))
        tbpfiles = list(new_state - old_state)
        
        if not len(tbpfiles):
            raise LogMinerError('Error: No anaconda traceback file exist')
            
        for file in tbpfiles:
            if file.startswith('anaconda-tb-'):
                tbpfile_name = file
                break
        else:
            raise LogMinerError('Error: No anaconda traceback file exist')
        
        # Copy anaconda traceback log
        self._write_files('/tmp/%s' % tbpfile_name)



class FileSystemLogMiner(LogMinerBaseClass):
    """Class represents way to get image of filesystem structure."""

    _name = "filesystem"
    _description = "Image of disc structure."
    _filename = "filesystem"
    _prefer_separate_file = True

    FSTREE_FORMAT = "%1s %6s%1s %s" # Format example: "d 1023.9K somedir"
    DADPOINT = 1                    # Number of Digits After the Decimal POINT

    def _action(self):
        self._get_tree_structure()

    def _size_conversion(self, size):
        """Converts bytes into KB, MB or GB"""
        if size >= 1073741824:  # Gigabytes
            size = round(size / 1073741824.0, self.DADPOINT)
            unit = "G"
        elif size >= 1048576:   # Megabytes
            size = round(size / 1048576.0, self.DADPOINT)
            unit = "M"
        elif size >= 1024:      # Kilobytes
            size = round(size / 1024.0, self.DADPOINT)
            unit = "K"
        else:
            size = size
            unit = ""
        return size, unit
    
    
    def _get_tree_structure(self, human_readable=True):
        """Creates filesystem structure image."""
        white_list = ['/sys']
        
        logfile = self.logfile
        
        for path, dirs, files in os.walk('/'):
            line = "\n%s:" % (path)
            logfile.write('%s\n' % line)
            
            # List dirs
            dirs.sort()
            for directory in dirs:
                fullpath = os.path.join(path, directory)
                size = os.path.getsize(fullpath)
                unit = ""
                if human_readable:
                    size, unit = self._size_conversion(size)
                line = self.FSTREE_FORMAT % ("d", size, unit, directory)
                logfile.write('%s\n' % line)
            
            # Skip mounted directories
            original_dirs = dirs[:]
            for directory in original_dirs:
                dirpath = os.path.join(path, directory)
                if os.path.ismount(dirpath) and not dirpath in white_list:
                    dirs.remove(directory)
            
            # List files
            files.sort()
            for filename in files:               
                fullpath = os.path.join(path, filename)
                if os.path.islink(fullpath):
                    line = self.FSTREE_FORMAT % ("l", "0", "", filename)
                    line += " -> %s" % os.path.realpath(fullpath)
                    if not os.path.isfile(fullpath):
                        # Broken symlink
                        line += " (Broken)"
                else:
                    stat_res = os.stat(fullpath)[stat.ST_MODE]
                    if stat.S_ISREG(stat_res):
                        filetype = "-"
                    elif stat.S_ISCHR(stat_res):
                        filetype = "c"
                    elif stat.S_ISBLK(stat_res):
                        filetype = "b"
                    elif stat.S_ISFIFO(stat_res):
                        filetype = "p"
                    elif stat.S_ISSOCK(stat_res):
                        filetype = "s"
                    else:
                        filetype = "-"
                    
                    size = os.path.getsize(fullpath)
                    unit = ""
                    if human_readable:
                        size, unit = self._size_conversion(size)
                    line = self.FSTREE_FORMAT % (filetype, size, unit, filename)
                logfile.write('%s\n' % line)



class DmSetupLsLogMiner(LogMinerBaseClass):
    """Class represents way to get 'dmsetup ls --tree' output."""

    _name = "dmsetup ls"
    _description = "Output from \"dmsetup ls --tree\"."
    _filename = "dmsetup-ls"
    _prefer_separate_file = True

    def _action(self):
        self._run_command("dmsetup ls --tree")


class DmSetupInfoLogMiner(LogMinerBaseClass):
    """Class represents way to get 'dmsetup info' output."""

    _name = "dmsetup info"
    _description = "Output from \"dmsetup info -c\"."
    _filename = "dmsetup-info"
    _prefer_separate_file = True

    def _action(self):
        self._run_command("dmsetup info -c")


ALL_MINERS = [AnacondaLogMiner(),
              FileSystemLogMiner(),
              DmSetupLsLogMiner(),
              DmSetupInfoLogMiner(),
             ]

