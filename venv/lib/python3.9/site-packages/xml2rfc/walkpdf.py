#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2018, All Rights Reserved

from __future__ import unicode_literals, print_function, division

import dict2xml
import io
import json
import lxml
import os
import pypdf
import sys

def walk(obj, seen):
    dobj = {}                            # Direct objects
    iobj = []                            # Indirect objects
    if isinstance(obj, pypdf.generic.DictionaryObject):
        for key in obj.keys():
            k = key[1:] if key.startswith('/') else key
            d, i = walk(obj[key], seen)
            dobj[k] = d
            iobj += i
        if hasattr(obj, 'extract_text'):
            dobj['text'] = obj.extract_text(extraction_mode="layout")
    elif isinstance(obj, pypdf.generic.ArrayObject):
        dobj = []
        for o in obj:
            d, i = walk(o, seen)
            dobj.append(d)
            iobj += i
    elif isinstance(obj, pypdf.generic.BooleanObject):
        dobj = obj.value
    elif isinstance(obj, pypdf.generic.NameObject):
        dobj = str(obj)
    elif isinstance(obj, pypdf.generic.NumberObject):
        dobj = int(obj)
    elif isinstance(obj, pypdf.generic.FloatObject):
        dobj = float(obj)
    elif isinstance(obj, pypdf.generic.IndirectObject):
        dobj = str(obj)
        if (obj.idnum, obj.generation) not in seen:
            seen.add((obj.idnum, obj.generation))
            d, i = walk(obj.get_object(), seen)
            if isinstance(d, dict):
                d['IdNum'] = obj.idnum
                d['Generation'] = obj.generation
            else:
                dobj = d
            iobj += i
            iobj.append(d)
    elif isinstance(obj, pypdf.generic.TextStringObject):
        dobj = str(obj)
    else:
        raise RuntimeError("Unexpected object type: %s" % type(obj))

    if hasattr(obj, 'idnum'):
        seen.add((obj.idnum, obj.generation))

    return dobj, iobj

def pyobj(filename=None, bytes=None):
    seen = set()
    #
    pdffile = io.BytesIO(bytes) if bytes else io.open(filename, 'br')
    reader = pypdf.PdfReader(pdffile, strict=False)
    info = reader.metadata
    doc = {}
    for key in info.keys():
        k = key[1:] if key.startswith('/') else key
        doc[k] = info[key]
    iobj = []
    pages = []
    for num in range(len(reader.pages)):
        page = reader.pages[num]
        obj = page.get_object()
        d, i = walk(obj, seen)
        #pages[num+1] = d
        pages.append(d)
        iobj += i
    pdffile.close()
    #
    doc['Page'] = pages
    doc['IndirectObject'] = iobj
    return doc

def xmltext(filename=None, obj=None, bytes=None):
    if obj is None:
        obj = pyobj(filename=filename, bytes=bytes)
#     for i,p in enumerate(obj['Pages']):
#         obj['Pages'][i] = {'Page': p}
    return dict2xml.dict2xml(obj, wrap="Document")    

def xmldoc(filename, text=None, bytes=None):
    if text is None:
        text = xmltext(filename=filename, bytes=bytes)
    return lxml.etree.fromstring(text)

def main():
    for filename in sys.argv[1:]:
        if not os.path.exists(filename):
            print('Could not find "%s"' % filename)
        print('File: %s' % filename)
        doc = pyobj(filename)
        with io.open(filename+'.json', 'w', encoding='utf-8') as j:
            json.dump(doc, j, indent=2)
        print('Wrote: %s' % j.name)
        with io.open(filename+'.xml', 'w', encoding='utf-8') as x:
            x.write(xmltext(filename, doc))
        print('Wrote: %s' % x.name)

if __name__ == "__main__":
    main()
