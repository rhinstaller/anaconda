import optparse
import log_picker.sending as sending


class ArgError(Exception):
    pass


class SimpleOptionGroup (optparse.OptionGroup):

    def _group_info_helper(self, formatter):
        res = ""
        lines = self.description.split('\n')
        for line in lines:
            res += formatter._format_text(line)
            res += '\n'
        return res

    def format_help(self, formatter):
        result = formatter.format_heading(self.title)
        formatter.indent()
        result += self._group_info_helper(formatter)
        formatter.dedent()
        return result


class _OptionParserWithRaise(optparse.OptionParser):
    def error(self, msg):
        raise ArgError(msg)


class ArgParser(object):
    
    def __init__(self):
        self.options = None
        self.parser = None
           
    
    def _generate_bz_it_group(self):
        if sending.RHBZ in sending.NOT_AVAILABLE and \
                                        sending.STRATA in sending.NOT_AVAILABLE:
            return None
        
        if sending.RHBZ in sending.NOT_AVAILABLE:
            title = "Send the report to the Red Hat Ticketing system | options"
            params_info = \
            "-r, --rhel                                                     \n"\
            "                    Send the report to the Red Hat Ticketing   \n"\
            "                    system.                                    \n"\
            "-i ID, --idbug=ID                                              \n"\
            "                    The case number in the Red Hat Ticketing   \n"\
            "                    system.                                    \n"\
            "-l USERNAME, --login=USERNAME                                  \n"\
            "                    Set the Red Hat Customer Portal username.  \n"
            
            bzg = SimpleOptionGroup(self.parser, title, params_info)
            bzg.add_option("-r", "--rhel", action="store_true", dest="strata")
            
        elif sending.STRATA in sending.NOT_AVAILABLE:
            title = "Send the report to the Bugzilla | options"
            params_info = \
            "-b, --bugzilla                                                 \n"\
            "                    Send the report to the Bugzilla.           \n"\
            "-i ID, --idbug=ID                                              \n"\
            "                    Set the bug id in the Bugzilla.            \n"\
            "-l USERNAME, --login=USERNAME                                  \n"\
            "                    Set the bugzilla username.                 \n"

            bzg = SimpleOptionGroup(self.parser, title, params_info)
            bzg.add_option("-b", "--bugzilla", action="store_true", 
                                                                dest="bugzilla")
            
        else:
            title = "Send the report to the Bugzilla or the Red Hat Ticketing" \
                                                            " system | options"
            params_info = \
            "-b, --bugzilla                                                 \n"\
            "                    Send the report to the Bugzilla.           \n"\
            "-r, --rhel                                                     \n"\
            "                    Send the report to the Red Hat Ticketing   \n"\
            "                    system.                                    \n"\
            "-i ID, --idbug=ID                                              \n"\
            "                    Set the bug id in the Bugzilla/Case number \n"\
            "                    in the  Red Hat Ticketing system.          \n"\
            "-l USERNAME, --login=USERNAME                                  \n"\
            "                    Set the Bugzilla/Red Hat Cutomer Portal    \n"\
            "                    username.                                  \n"
            
            bzg = SimpleOptionGroup(self.parser, title, params_info)
            bzg.add_option("-b", "--bugzilla", action="store_true", 
                                                                dest="bugzilla")
            bzg.add_option("-r", "--rhel", action="store_true", dest="strata")
                                    
        bzg.add_option("-i", "--idbug", dest="bug_id", metavar="ID")
        bzg.add_option("-l", "--login", dest="login", metavar="USERNAME")

        return bzg
    
    
    def _generate_email_group(self):
        if sending.EMAIL in sending.NOT_AVAILABLE:
            return None
        
        title = "Send the report to an email | options"
        params_info = \
        "-e, --email                                                        \n"\
        "                    Send the report to an email address.           \n"\
        "-s ADDRESS, --server=ADDRESS                                       \n"\
        "                    Set the SMTP server address.                   \n"\
        "-f EMAIL, --from=EMAIL                                             \n"\
        "                    Set your email address.                        \n"\
        "-t EMAIL, --to=EMAIL                                               \n"\
        "                    Set the destination email address.             \n"

        
        emailg = SimpleOptionGroup(self.parser, title, params_info)
        emailg.add_option("-e", "--email", action="store_true", dest="email")
        emailg.add_option("-s", "--server", dest="smtp_addr", metavar="ADDRESS")
        emailg.add_option("-f", "--from", dest="from_addr", metavar="EMAIL")
        emailg.add_option("-t", "--to", dest="to_addr", metavar="EMAIL")
        return emailg
    
    
    def _generate_scp_group(self):
        if sending.SCP in sending.NOT_AVAILABLE:
            return None
        
        title = "Send the report via secure copy (scp) | options"
        params_info = \
        "-o, --scp                                                          \n"\
        "                    Send the report to the remote computer via scp.\n"\
        "-l USERNAME, --login=USERNAME                                      \n"\
        "                    Set the remote username.                       \n"\
        "-a HOST, --host=HOST                                               \n"\
        "                    Set the remote host address.                   \n"\
        "-p PATH, --path=PATH                                               \n"\
        "                    Set the file path on the remote host.          \n"
        
        scpg = SimpleOptionGroup(self.parser, title, params_info)
        scpg.add_option("-o", "--scp", action="store_true", dest="scp")
        scpg.add_option("-l", "--login", dest="login", metavar="USERNAME")
        scpg.add_option("-a", "--host", dest="host", metavar="HOST")
        scpg.add_option("-p", "--path", dest="path", metavar="PATH")
        return scpg


    def _generate_ftp_group(self):
        if sending.FTP in sending.NOT_AVAILABLE:
            return None
        
        title = "Upload the report via FTP | options"
        params_info = \
        "-q, --ftp                                                          \n"\
        "                    Upload the report via ftp.                     \n"\
        "-l USERNAME, --login=USERNAME                                      \n"\
        "                    Set the ftp username.                          \n"\
        "                    Note: For anonymous login don't use this option\n"\
        "-a HOST, --host=HOST                                               \n"\
        "                    Set the remote host address.                   \n"\
        "                    Address syntax: [ftp://]host[:port][path]      \n"\
        "                    Examples of host addresses:                    \n"\
        "                      host.com, ftp://host.com:21/path/on/the/host \n"
        
        ftpg = SimpleOptionGroup(self.parser, title, params_info)
        ftpg.add_option("-q", "--ftp", action="store_true", dest="ftp")
        ftpg.add_option("-l", "--login", dest="login", metavar="USERNAME")
        ftpg.add_option("-a", "--host", dest="host", metavar="HOST")
        return ftpg


    def _generate_local_group(self):
        if sending.LOCAL in sending.NOT_AVAILABLE:
            return None
        
        title = "Save the report to the local computer | options"
        params_info = \
        "-m, --local                                                        \n"\
        "                    Save the report to a directory on the computer.\n"\
        "-p DIRECTORY, --path=DIRECTORY                                     \n"\
        "                    Set the local directory.                       \n"
        
        localg = SimpleOptionGroup(self.parser, title, params_info)
        localg.add_option("-m", "--local", action="store_true", dest="local")
        localg.add_option("-p", "--path", dest="path", metavar="PATH")
        return localg


    def _create_parser(self):
        self.parser = _OptionParserWithRaise(conflict_handler="resolve")
        self.parser.add_option("-c", "--comment", dest="bug_comment", 
                        default=None, help="Report comment.", metavar="COMMENT")
        
        # Bugzilla and Red Hat Ticketing system options
        group = self._generate_bz_it_group()
        if group: self.parser.add_option_group(group)
        
        # Email options
        group = self._generate_email_group()
        if group: self.parser.add_option_group(group)
        
        # Scp options
        group = self._generate_scp_group()
        if group: self.parser.add_option_group(group)

        # Ftp options
        group = self._generate_ftp_group()
        if group: self.parser.add_option_group(group)        
        
        # Local options
        group = self._generate_local_group()
        if group: self.parser.add_option_group(group)

    def _parse(self):
        (self.options, _) = self.parser.parse_args()
        
        # Set sender attribute
        if self.options.ensure_value('email', None):
            self.options.sender = sending.EMAIL
        elif self.options.ensure_value('strata', None):
            self.options.sender = sending.STRATA
        elif self.options.ensure_value('bugzilla', None):
            self.options.sender = sending.RHBZ
        elif self.options.ensure_value('scp', None):
            self.options.sender = sending.SCP
        elif self.options.ensure_value('ftp', None):
            self.options.sender = sending.FTP
        elif self.options.ensure_value('local', None):
            self.options.sender = sending.LOCAL
        else:
            self.options.sender = None
      
    def _validate(self):
        cnt = 0
        if self.options.ensure_value('email', None): cnt += 1
        if self.options.ensure_value('bugzilla', None): cnt += 1
        if self.options.ensure_value('strata', None): cnt += 1
        if self.options.ensure_value('scp', None): cnt += 1
        if self.options.ensure_value('ftp', None): cnt += 1
        if self.options.ensure_value('local', None): cnt += 1
        
        if not cnt:
            raise ArgError("No send method selected.")
        elif cnt > 1:
            raise ArgError("Options -b, -r, -e, -o, -q and -m" \
                                                    " are mutually exclusive.")
        
        missing = []
        if self.options.ensure_value('email', None):
            if not self.options.smtp_addr: missing.append('-s')
            if not self.options.from_addr: missing.append('-f')
            if not self.options.to_addr: missing.append('-t')
        elif self.options.ensure_value('bugzilla', None):
            if not self.options.bug_id: missing.append('-i')
            if not self.options.login: missing.append('-l')
        elif self.options.ensure_value('strata', None):
            if not self.options.bug_id: missing.append('-i')
            if not self.options.login: missing.append('-l')
        elif self.options.ensure_value('scp', None):
            if not self.options.login: missing.append('-l')
            if not self.options.host: missing.append('-a')
        elif self.options.ensure_value('ftp', None):
            if not self.options.host: missing.append('-a')
        elif self.options.ensure_value('local', None):
            if not self.options.path: missing.append('-p')
                
        if missing:
            msg = ""
            for arg in missing:
                msg += '\nArgument "%s" is missing!' % arg
            raise ArgError(msg)
    
    
    def parse(self):
        """Parse and validate command line arguments."""
        self._create_parser()
        self._parse()
        self._validate()
        return self.options

