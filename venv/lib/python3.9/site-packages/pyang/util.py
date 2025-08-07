import os.path
import sys
from numbers import Integral as int_types

from .error import err_add


def attrsearch(tag, attr, in_list):
    for x in in_list:
        if getattr(x, attr) == tag:
            return x
    return None


def keysearch(tag, n, in_list):
    for x in in_list:
        if x[n] == tag:
            return x
    return None


def dictsearch(val, in_dict):
    for key in in_dict:
        if in_dict[key] == val:
            return key
    return None


def is_prefixed(identifier):
    return isinstance(identifier, tuple) and len(identifier) == 2


def is_local(identifier):
    return isinstance(identifier, str)


def split_identifier(identifier):
    idx = identifier.find(":")
    if idx == -1:
        return None, identifier
    return identifier[:idx], identifier[idx + 1:]


def keyword_to_str(keyword):
    if keyword == '__tmp_augment__':
        return "undefined"
    elif is_prefixed(keyword):
        (prefix, keyword) = keyword
        return prefix + ":" + keyword
    else:
        return keyword


def guess_format(text):
    """Guess YANG/YIN format

    If the first non-whitespace character is '<' then it is XML.
    Return 'yang' or 'yin'"""
    for char in text:
        if not char.isspace():
            if char == '<':
                return 'yin'
            break
    return 'yang'


def get_latest_revision(module):
    revisions = [revision.arg for revision in module.search('revision')]
    return max(revisions) if revisions else 'unknown'


# module is the (sub)module where the statement is defined
def prefix_to_modulename_and_revision(module, prefix, pos, errors):
    if prefix == '' or prefix == module.i_prefix:
        if module.i_version == '1':
            return module.arg, None
        return module.i_main_module.arg, None
    try:
        (modulename, revision) = module.i_prefixes[prefix]
    except KeyError:
        if prefix not in module.i_missing_prefixes:
            err_add(errors, pos, 'PREFIX_NOT_DEFINED', prefix)
        module.i_missing_prefixes[prefix] = True
        return None, None
    # remove the prefix from the unused
    if prefix in module.i_unused_prefixes:
        del module.i_unused_prefixes[prefix]
    return modulename, revision

# module is the (sub)module where the statement is defined
def prefix_to_module(module, prefix, pos, errors):
    if prefix == '' or prefix == module.i_prefix:
        if module.i_version == '1':
            return module
        return module.i_main_module
    modulename, revision = \
        prefix_to_modulename_and_revision(module, prefix, pos, errors)
    if modulename is None:
        return None
    return module.i_ctx.get_module(modulename, revision)


def unique_prefixes(context):
    """Return a dictionary with unique prefixes for modules in `context`.

    Keys are 'module' statements and values are prefixes,
    disambiguated where necessary.
    """
    modules = sorted(context.modules.values(), key=lambda module: module.arg)
    prefixes = set()
    conflicts = []
    result = {}

    for module in modules:
        if module.keyword == "submodule":
            continue
        prefix = module.i_prefix
        if prefix in prefixes:
            conflicts.append(module)
        else:
            result[module] = prefix
            prefixes.add(prefix)

    for module in conflicts:
        prefix = module.i_prefix
        append = 0
        while True:
            append += 1
            candidate = "%s%x" % (prefix, append)
            if candidate not in prefixes:
                break
        result[module] = candidate
        prefixes.add(candidate)

    return result


files_read = {}

def report_file_read(filename, extra=None):
    realpath = os.path.realpath(filename)
    read = "READ" if realpath in files_read else "read"
    extra = (" " + extra) if extra else ""
    sys.stderr.write("# %s %s%s\n" % (read, filename, extra))
    files_read[realpath] = True


def search_data_node(children, modulename, identifier, last_skipped = None):
    skip = ['choice', 'case', 'input', 'output']
    if last_skipped is not None:
        skip.append(last_skipped)
    for child in children:
        if child.keyword in skip:
            r = search_data_node(child.i_children,
                                 modulename, identifier)
            if r is not None:
                return r
        elif ((child.arg == identifier) and
              (child.i_module.i_modulename == modulename)):
            return child
    return None


def closest_ancestor_data_node(node):
    if node.keyword in ['choice', 'case']:
        return closest_ancestor_data_node(node.parent)
    return node


def data_node_up(node):
    skip = ['choice', 'case', 'input', 'output']
    p = node.parent
    if node.keyword in skip:
        return data_node_up(p)
    if p and p.keyword in skip:
        return closest_ancestor_data_node(p)
    return p
