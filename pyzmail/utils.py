#
# pyzmail/utils.py
# (c) Alain Spineux <alain.spineux@gmail.com>
# http://www.magiksys.net/pyzmail
# Released under LGPL

"""
Various functions used by other modules
@var invalid_chars_in_filename: a mix of characters not permitted in most used filesystems
@var invalid_windows_name: a list of unauthorized filenames under Windows
"""

import sys

invalid_chars_in_filename=b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f' \
                          b'\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f' \
                          b'<>:"/\\|?*%\''

invalid_windows_name=[b'CON', b'PRN', b'AUX', b'NUL', b'COM1', b'COM2', b'COM3', 
                      b'COM4', b'COM5', b'COM6', b'COM7', b'COM8', b'COM9', 
                      b'LPT1', b'LPT2', b'LPT3', b'LPT4', b'LPT5', b'LPT6', b'LPT7',
                      b'LPT8', b'LPT9' ]

def sanitize_filename(filename, alt_name, alt_ext):
    """
    Convert the given filename into a name that should work on all 
    platform. Remove non us-ascii characters, and drop invalid filename.
    Use the I{alternative} filename if needed.
    
    @type filename: unicode or None
    @param filename: the originale filename or None. Can be unicode.
    @type alt_name: str
    @param alt_name: the alternative filename if filename is None or useless
    @type alt_ext: str
    @param alt_ext: the alternative filename extension (including the '.')

    @rtype: str
    @returns: a valid filename.
     
    >>> sanitize_filename('document.txt', 'file', '.txt')
    'document.txt'
    >>> sanitize_filename('number1.txt', 'file', '.txt')
    'number1.txt'
    >>> sanitize_filename(None, 'file', '.txt')
    'file.txt'
    >>> sanitize_filename(u'R\\xe9pertoir.txt', 'file', '.txt')
    'Rpertoir.txt'
    >>> # the '\\xe9' has been removed
    >>> sanitize_filename(u'\\xe9\\xe6.html', 'file', '.txt')
    'file.html'
    >>> # all non us-ascii characters have been removed, the alternative name
    >>> # has been used the replace empty string. The originale extention
    >>> # is still valid  
    >>> sanitize_filename(u'COM1.txt', 'file', '.txt')
    'COM1A.txt'
    >>> # if name match an invalid name or assimilated then a A is added
    """
    
    if not filename:
        return alt_name+alt_ext

    if ((sys.version_info<(3, 0) and isinstance(filename, str)) or \
        (sys.version_info>=(3, 0) and isinstance(filename, str))):
        filename=filename.encode('ascii', 'ignore')
    
    filename=filename.translate(None, invalid_chars_in_filename)
    filename=filename.strip()
        
    upper=filename.upper()
    for name in invalid_windows_name:
        if upper==name:
            filename=filename+b'A'
            break
        if upper.startswith(name+b'.'):
            filename=filename[:len(name)]+b'A'+filename[len(name):]
            break

    if sys.version_info>=(3, 0):
        # back to string
        filename=filename.decode('us-ascii')

    if filename.rfind('.')==0:
        filename=alt_name+filename

    return filename

def handle_filename_collision(filename, filenames):
    """
    Avoid filename collision, add a sequence number to the name when required.
    'file.txt' will be renamed into 'file-01.txt' then 'file-02.txt' ... 
    until their is no more collision. The file is not added to the list.
     
    Windows don't make the difference between lower and upper case. To avoid
    "case" collision, the function compare C{filename.lower()} to the list.
    If you provide a list in lower case only, then any collisions will be avoided.     
    
    @type filename: str
    @param filename: the filename
    @type filenames: list or set
    @param filenames: a list of filenames. 

    @rtype: str
    @returns: the I{filename} or the appropriately I{indexed} I{filename} 
     
    >>> handle_filename_collision('file.txt', [ ])
    'file.txt'
    >>> handle_filename_collision('file.txt', [ 'file.txt' ])
    'file-01.txt'
    >>> handle_filename_collision('file.txt', [ 'file.txt', 'file-01.txt',])
    'file-02.txt'
    >>> handle_filename_collision('foo', [ 'foo',])
    'foo-01'
    >>> handle_filename_collision('foo', [ 'foo', 'foo-01',])
    'foo-02'
    >>> handle_filename_collision('FOO', [ 'foo', 'foo-01',])
    'FOO-02'
    """
    if filename.lower() in filenames:
        try:
            basename, ext=filename.rsplit('.', 1)
            ext='.'+ext
        except ValueError:
            basename, ext=filename, '' 

        i=1
        while True:
            filename='%s-%02d%s' % (basename, i, ext)
            if filename.lower() not in filenames:
                break
            i+=1
        
    return filename

def is_usascii(value):
    """"
    test if string contains us-ascii characters only
    
    >>> is_usascii('foo')
    True
    >>> is_usascii(u'foo')
    True
    >>> is_usascii(u'Fran\xe7ais')
    False
    >>> is_usascii('bad\x81')
    False
    """
    try:
        # if value is byte string, it will be decoded first using us-ascii
        # and will generate UnicodeEncodeError, this is fine too
        value.encode('us-ascii')
    except UnicodeError:
        return False
    
    return True
 