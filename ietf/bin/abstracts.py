#!/usr/bin/env python
from django.conf import settings
from django.template.loader import render_to_string
from ietf.idtracker.models import InternetDraft, Area, Acronym, AreaGroup, IETFWG, IDAuthor
import sys, os, getopt, re

def group_string(group):
    text = group.group_acronym.name + " (" + group.group_acronym.acronym + ")"
    return text

def dashes_for_string(string):
    return len(string) * "-"

def draft_authors(draft):
    authors = IDAuthor.objects.filter(document=draft).order_by('author_order')
    author_names = []
    for author in authors:
        author_names.append(author.person.first_name + " " + author.person.last_name)
    return ", ".join(author_names)

def draft_title_text(draft):
    title = "\"" + draft.title + "\""
    return title

def rewrap(text, width=72, indent=0):
    paras = text.strip().split("\n\n")
    lwidth = width - indent
    join_str = "\n" + " " * indent
    for i in range(len(paras)):
        para = paras[i]
        while re.search("([^\n]{%s,}?) +"%lwidth, para):
            para = re.sub("([^\n]{%s,}?) +([^\n ]*)(\n|$)"%lwidth, "\g<1>\n\g<2> ", para)
        paras[i] = join_str + join_str.join(para.split('\n'))
    text = "\n\n".join(paras)
    return text

def tounix(text):
    # split into dos or mac lines.
    # (This is a no-op if the text is already unix text)
    def nlstrip(line):
        if line.startswith("\n"):
            return line[1:]
        else:
            return line
    lines = text.split("\r")
    lines = [ lines[0] ] + [ nlstrip(line) for line in lines[1:] ]
    return "\n".join(lines)

def wrap_and_indent(text, width=74, indent=0):
    result = []
    cur_line_words = []
    words = text.split()
    cur_len = 0
    for word in words:
        if cur_len + len(word) + indent < width:
            cur_line_words.append(word)
            cur_len = cur_len + len(word) + 1
        else:
            result.append(indent*" " + " ".join(cur_line_words))
            cur_line_words = [word]
            cur_len = len(word) + 1
    if len(cur_line_words) > 0:
        result.append(indent*" " + " ".join(cur_line_words))
    return "\n".join(result)

def draft_abstract_text(draft):
    # this function does nothing at the moment,
    # but cleanup functionality on the abstract
    # text should go here (like removing ^M etc)
    return rewrap(tounix(draft.abstract), 72, 4)

# sort key for the output group List, as the database model
# does not seem to easily allow sorting by acronym
def group_sort_key(group_elements):
    return group_elements['acronym']

# if txt_filename is not None, .txt output will be written to
# that file
# if idindex_filename is not None, idlist .txt output will be written to
# that file
# if html_filename is not None (eg. 1id_abstracts.html), an overview
# will be written to this file
# if html_directory is not None, html files per group will
# be created in this directory, and an overview will be
def create_abstracts_text(acronym, idindex_filename, txt_filename, html_filename, html_directory, silent=False):
    # if you want to store everythinh in a string instead of printing,
    # remember not to use str + str, but make a list for it and use join()
    if acronym:
        groups = IETFWG.objects.filter(areagroup__area__area_acronym__acronym=acronym).order_by('group_acronym')
        if len(groups) == 0:
          print "Error: unknown area acronym or area has no groups"
          sys.exit()
    else:
        groups = IETFWG.objects.all();

    group_elements = []

    for group in groups:
        if not silent:
            print group.group_acronym.acronym

        drafts = group.active_drafts()

        if len(drafts) > 0:
            group_text = group_string(group)
            
            draft_elements = []

            for draft in drafts:
                title_text = draft_title_text(draft)
                authors_text = draft_authors(draft)
                abstract_text = draft_abstract_text(draft)

                title_parts = []
                title_parts.append(title_text)
                title_parts.append(authors_text)
                title_parts.append(str(draft.revision_date))
                title_parts.append("<" + draft.filename + "-" + draft.revision + ".txt" + ">")
                    
                # if wrap_and_indent is implemented as a template function
                # we wouldn't need the title_all here
                draft_elements.append({'title': title_text,
                                       'authors': authors_text,
                                       'rev_date': draft.revision_date,
                                       'filename': draft.filename + "-" + draft.revision + ".txt",
                                       'title_all': wrap_and_indent(", ".join(title_parts), 80, 2),
                                       'abstract': abstract_text
                                       #'abstract': wrap_and_indent(abstract_text, 80, 4)
                                      })
            
            if html_directory:
                rel_url = html_directory + "/" + group.group_acronym.acronym + ".html"
            else:
                rel_url = ""
            
            group_elements.append({'name': group_text,
                     'dashes': dashes_for_string(group_text),
                     'acronym': group.group_acronym.acronym,
                     'rel_url': rel_url,
                     'drafts': draft_elements,
                     'active_draft_count': len(drafts)
                     })

            if html_directory:
                group_html_file = open(html_directory + os.sep + group.group_acronym.acronym + ".html", "w")
                group_html_file.write(render_to_string("idtracker/idtracker_abstracts_group.html", {'drafts': draft_elements}))
                group_html_file.close()

    group_elements.sort(key=group_sort_key)
    if txt_filename:
        txt_file = open(txt_filename, "w")
        txt_file.write(render_to_string("idtracker/idtracker_abstracts.txt", {'groups': group_elements}))
        txt_file.close()

    if idindex_filename:
        idindex_file = open(idindex_filename, "w")
        idindex_file.write(render_to_string("idtracker/idtracker_idlist.txt", {'groups': group_elements}))
        idindex_file.close()

    if html_filename:
        html_file = open(html_filename, "w")
        html_file.write(render_to_string("idtracker/idtracker_abstracts.html", {'groups': group_elements}))
        html_file.close()

def usage():
    print "Usage: abstracts [OPTIONS]"
    print ""
    print "Options:"
    print ""
    print "-a, --area=<area>\tOnly handle groups and drafts from area acronym"
    print "                                 \t(defaults to all)"
    print "-d, --htmldir=<dir>\tCreate group-specific html pages in dir"
    print "-f, --htmlfile=<file>\tWrite HTML index of groups to file"
    print "-h, --help\t\tShow this help"
    print "-i, --idindex=<file>\tCreate ID index txt list in file"
    print "-q, --silent\t\tDo not show progress"
    print "-t, --txtfile=<file>\tWrite abstract list to file"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "a:d:f:hi:qt:", ["area=", "htmldir=", "htmlfile=", "help=", "idindex=", "silent=", "txtfile="])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    
    html_directory = None
    html_file = None
    idindex_file = None
    silent = False
    txt_file = None
    area_acronym = None
    
    for o, a in opts:
        if o in ("-a", "--area"):
            area_acronym = a
        elif o in ("-d", "--htmldir"):
            html_directory = a
        elif o in ("-f", "--htmlfile"):
            html_file = a
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-i", "--idindex"):
            idindex_file = a
        elif o in ("-q", "--silent"):
            silent = True
        elif o in ("-t", "--txtfile"):
            txt_file = a
        else:
            assert False, "Unrecognized option" + o
    
    if (html_directory and not html_file) or not html_directory and html_file:
        print ""
        print "Error: when using one of -d and -f, the other must be used too"
        print ""
        usage()
    if (html_directory and html_file) or idindex_file or txt_file:
        if html_directory and not os.path.exists(html_directory):
            os.mkdir(html_directory)
        if html_directory and not os.path.isdir(html_directory):
            print "Error: ", html_directory, "exists, but is not a directory"
            sys.exit()
        create_abstracts_text(area_acronym, idindex_file, txt_file, html_file, html_directory, silent)
    else:
        print ""
        print "Error: either -t, -i or both -d and -f must be specified"
        print ""
        usage()
        sys.exit()


if __name__ == "__main__":
    main()
