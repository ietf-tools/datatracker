from ietf.submit.parsers.base import FileParser

class PSParser(FileParser):
    
    def parse_critical_filename_extension(self):
        if not self.fd.name.endswith('.ps'):
            self.parsed_info.add_error('Format of this document must be PS')
