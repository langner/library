#!/usr/bin/env pybliographer

import StringIO

import os
import sys
import time
import urllib

import xml.dom.minidom

import Levenshtein

from Pyblio.Format import BibTeX


# ##################
# Global definitions
# ##################

# Path to the bibliography file, assumed to be in the same directory as this script.
bibfile = os.path.abspath(os.path.join(os.path.dirname(sys.argv[1])))+"/library.bib"

# Permissible extensions for local files.
formats = ('.pdf', '.ps')


# ###################
# Auxiliary functions
# ###################

# Note: I used this in the past, now I usually create keys manually.
def std_id(entry, n=0):
    """ Generate standardized bibtex keys. """

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

# Note: I used this in the past, now I mostly get DOIs from Zotero or input them by hand.
def getdoi(emailfile=".email", journal=False, volume=False, issue=False, spage=False, date=False):
    """
    Fetch DOIs automatically from crossref for a large number of articles.
    The email address is read from a file assumed to consist of a single line.
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
    """
    Searches for a local file in all subdirectories, returning and setting the first one found.
    Looks for entry key, or "<year> - <title>" format and Levenshtein distances in fuzzy search.
    """

    if not entry.has_key('date'):
        return None

    full = "%s - %s" %(entry['date'].year, entry['title'])
    full = full.replace('{','').replace('}','')

    subdirs = os.listdir('.')
    for subdir in subdirs:

        path = "%s" %subdir
        if not os.path.isdir(path):
            continue;

        fnames = [fn for fn in os.listdir(path) if os.path.splitext(fn)[1] in formats]
        if len(fnames) == 0:
            continue;

        keypdf = entry.key.key+".pdf"
        if keypdf in fnames:
            fname = fnames[fnames.index(keypdf)]
            path +=  "/%s" %fname
            entry['localfile'] = path
            return path

        ratios = [Levenshtein.ratio(os.path.splitext(fn)[0].lower(),full.lower()) for fn in fnames]
        contain = [os.path.splitext(fn)[0].lower() in full.lower() for fn in fnames]

        if max(ratios) > 0.8:
            fname = fnames[ratios.index(max(ratios))]
            path += "/%s" %fname
            entry['localfile'] = path
            return path

        if contain.count(True) != 0:
            fname = fnames[contain.index(True)]
            path += "/%s" %fname
            entry['localfile'] = path
            return path

    return None

def writebib(db, fname):
    """
    Write a database to file, with the following tweaks:
        - sort alphanumericcally by keys
        - single empty lines between entries
        - all fields are on single lines
        - no comments
    """

    # Write the database to a string, in alphanumerical order.
    text = StringIO.StringIO()
    keys = db.dict.keys()
    keys.sort()
    for key in keys:
        BibTeX.entry_write(db[key], text)
    text.seek(0)

    # Now do the actualy printing, with tweaks.
    f = open(fname,'w')
    multiline = {}
    for line in text:

        # Skip empty lines and comments.
        if not line.strip() or line[0:8] == "@comment":
            continue;

        # Append line to multiline until brace is met, then print.
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

        # Add an extra empty lines after closing braces.
        if line.strip() == "}":
            print >>f, ""

    f.close()


if __name__ == "pybliographer":

    # Fix the database, that is rewrite with sorting and other tweaks,
    #  and look for missing local files.
    if "fix" in sys.argv:

        db = bibopen(bibfile)
        newdb = Base.DataBase(db.key)
        for key,entry in db.dict.iteritems():
            if not entry.has_key('localfile') or not os.path.exists(str(entry['localfile'])):
                entry['localfile'] = ""
                if find_localfile(entry):
                    print "  %s: set localfile" %(key.key)
            newdb[key] = entry
        writebib(newdb, bibfile)

    # Split the main file into smaller ones. This actually saves a subset
    #  of the entries that contain any of the given keywords, so the
    #  script need to be called with this option multiple times in order
    #  to really split the entire file into pieces (via Makefile, for example).
    if "split" in sys.argv:

        splitfile = sys.argv[3]
        if len(sys.argv) > 4:
            subjects = sys.argv[4:]
        else:
            subjects = [splitfile.split('/')[0]]

        db = bibopen(bibfile)
        newdb = Base.DataBase(db.key)

        for key,entry in db.dict.iteritems():
            if any([s in entry['subjects'].text.split(', ') for s in subjects]):
                if entry.has_key('localfile') and entry['localfile'].text.strip():
                    entry['localfile'] = entry['localfile'].text.split('/')[1]
                    entry.__delitem__("subjects")
                newdb[key] = entry

        writebib(newdb, splitfile)