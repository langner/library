#!/usr/bin/env pybliographer

"""
I use this script to organize my collection of references.

There is one big file of BibTeX references (library.bib),
and a smaller version (library.small.bib) that contains a subset
of all the fields (I leave out abstract and localfile).

This script has two main functions:
 fix    -- reads in the big file, formats it, and write it back file
 divide -- splits the main file into smaller ones, with one file
           for each unique value of the collection field saved
           in a subdirectory of the same name
"""


import StringIO

import os
import sys
import time
import urllib

import xml.dom.minidom

import Levenshtein

from Pyblio.Format import BibTeX

license = """
This BibTeX file is made available under the Public Domain Dedication and License v1.0 whose full text can be found in the accompanying README file or online at http://www.opendatacommons.org/licenses/pddl/1.0/
"""


# ##################
# Global definitions
# ##################

# The bibliography file is assumed to be in the same directory as this script.
bibfile = os.path.abspath(os.path.join(os.path.dirname(sys.argv[1])))+"/library.bib"

# These are the permissible extensions for local files.
formats = ('.pdf', '.ps')


# ###################
# Auxiliary functions
# ###################

def std_id(entry, n=0):
    """ Generate standardized bibtex keys.

    This was helpful, but now I create keys manually, because of problems
    related to duplicate keys.

    I add a number to the end of the key when the standard format is
    a duplicate of an existing key. When done automatically, however
    the order of these duplicates is hard to control. So, if a new entry
    happens to be before on older entry with the same standard key,
    it will take its place and the older entry will be renamed.
    This is utterly confusing when I've used the old key for several
    years in the standard format.
    """

    auth = entry['author'][0].last.split()[-1]
    if len(entry['author']) == 2:
        auth += "-%s" %entry['author'][1].last.split()[-1]
    if len(entry['author']) > 2:
        auth += "-%s" %"".join([a.last.split()[-1][0] for a in entry['author'][1:]])
    if entry.has_key('date'):
        key = "%s-%s" %(entry['date'].year,auth)
        if n > 0:
            key += "-%i" %n
        return Base.Entry(key, entry.key.base)
    else:
        return None

def getdoi(emailfile=".email", journal=False, volume=False, issue=False, spage=False, date=False):
    """ Fetch DOIs automatically from crossref for a large number of articles.

    The email address is read from a file assumed to consist of a single line.

    I used this in the past, now I mostly import entries or retrieve DOIs manually.
    """

    journal = journal.replace(" ", "%20")
    url = "http://www.crossref.org/openurl?pid=%s" %open(emailfile).read().strip()

    if journal:
        url += "&title=%s" %journal
    if volume:
        url += "&volume=%s" %volume
    if issue:
        url += "&issue=%s" %issue
    if spage:
        url += "&spage=%s" %spage
    if date:
        url += "&date=%s" %date
    url += "&redirect=false&format=unixref"

    txt = urllib.urlopen(url).read()
    doc = xml.dom.minidom.parseString(txt)
    dois = doc.getElementsByTagName('doi')
    dois = [doi.childNodes[0].nodeValue for doi in dois]

    return dois

def find_localfile(entry):
    """ Search for a local file corresponding to a given key

    Looks in all subdirectories, returning and setting the first file
    that seems to fit. The entry key is considered a candidate, but normally
    I use the rule "<year> - <title>" for filenames, with a fuzzy search
    based on Levenshtein distances. If both exist, however, the rule should
    always take precedence over the entry key.
    """

    if not entry.has_key('date'):
        return None

    expected_filename = "%s - %s" %(entry['date'].year, entry['title'])
    expected_filename = expected_filename.replace('{','').replace('}','')

    for subdir in os.listdir('.'):

        if not os.path.isdir(subdir):
            continue;

        fnames = [fn for fn in os.listdir(subdir) if os.path.splitext(fn)[1] in formats]
        fnames_noext = [os.path.splitext(fn)[0] for fn in fnames]
        if len(fnames) == 0:
            continue;

        if entry.key.key in fnames_noext:
            localfname = fnames[fnames_noext.index(entry.key.key)]

        get_ratio = lambda s1, s2: Levenshtein.ratio(s1.lower(), s2.lower())
        ratios = [get_ratio(fn, expected_filename) for fn in fnames_noext]
        if max(ratios) > 0.8:
            localfname = fnames[ratios.index(max(ratios))]

        contain = [fn.lower() in expected_filename.lower() for fn in fnames_noext]
        if contain.count(True) != 0:
            localfname = fnames[contain.index(True)]

        if 'localfname' in locals():
            path =  "%s/%s" %(subdir, localfname)
            entry['localfile'] = path
            return path

    return None

def writebib(db, fname):
    """ Write a database to file.

    This includes several tweaks:
        - sort alphanumerically by entry keys
        - add single empty lines between entries
        - all fields are on single lines, no matter how long they are
        - add an open license at top of file as a comment
        - elliminate all other comments from the file
    """

    # First write the database to a single string, in alphanumerical order.
    text = StringIO.StringIO()
    keys = db.dict.keys()
    keys.sort()
    for key in keys:
        BibTeX.entry_write(db[key], text)
    text.seek(0)

    # Now do the actualy printing, with tweaks.
    # At the beginning, print the license to the file.
    f = open(fname,'w')
    print >>f, license

    multiline = {}
    for line in text:

        if not line.strip() or line[0:8] == "@comment":
            continue;

        # Append the line to multiline until a brace is met, then print everything.
        if multiline:
            multiline[key] += " " + line.strip()
            if line.strip()[-2] in ('"','}'):
                for key in multiline:
                    print >>f, "\t%s = %s" %(key, multiline[key])
                multiline = {}
            continue;

        # Format and print line, initiate an element in multiline when needed.
        if len(line.split()) > 1 and line.split()[1] == "=":
            key = line.split()[0]
            value = " ".join(line.split()[2:])
            if len(value.split()) > 1:
                if value[0] in ('"','{') and not value.strip()[-2] in ('"','}'):
                    multiline[key] = value.strip()
                    continue;
            print >>f, "\t%s = %s" %(key,value)
            continue;

        # Print line with entry header or closing braces (only ones left).
        print >>f, line.strip()

        # Add an extra empty line after closing braces.
        if line.strip() == "}":
            print >>f, ""

    f.close()


if __name__ == "pybliographer":

    # When reformatting the library file, abort if there is any entry without
    # the collection field -- all entries should have this field.
    # Also, try to find a local file and set the localfile field if one can be found.
    if "fix" in sys.argv:

        db = bibopen(bibfile)
        newdb = Base.DataBase(db.key)
        for key,entry in db.dict.iteritems():

            if not entry.has_key("collection"):
                raise KeyError, "Missing collection field in: %s" %key.key

            if not entry.has_key('localfile') or not os.path.exists(str(entry['localfile'])):
                entry['localfile'] = ""
                if find_localfile(entry):
                    print "  %s: set localfile" %(key.key)

            newdb[key] = entry

        writebib(newdb, bibfile)

    # Splitting the main file into smaller ones is based on the collection field.
    # This code actually extracts a subset of the database based on one collection
    # value, so run this script many times to divide the entire database among
    # all possible values of collections (via Makefile, for example).
    if "split" in sys.argv:

        splitfile = sys.argv[3]
        if len(sys.argv) > 4:
            collection = sys.argv[4:]
        else:
            collection = [splitfile.split('/')[0]]

        db = bibopen(bibfile)
        newdb = Base.DataBase(db.key)

        for key,entry in db.dict.iteritems():
            if any([s in entry['collection'].text.split(', ') for s in collection]):
                if entry.has_key('localfile') and entry['localfile'].text.strip():
                    entry['localfile'] = entry['localfile'].text.split('/')[1]
                    entry.__delitem__("collection")
                newdb[key] = entry

        writebib(newdb, splitfile)
