import fileinput
from random import getrandbits

from lxml import etree


def main():
    # This is for ListenNotes OPML exports.
    # I have no idea how to work with XML, this lxml code is
    # probably really dumb.
    root = etree.fromstring("".join(line for line in fileinput.input()))
    for a in root.iterchildren():
        if a.tag == "body":
            for b in a.iterchildren():
                print(b.attrib["xmlUrl"])
                # for aria2c --input-file
                # just to make sure filenames don't clobber
                print(f" out=podcast-{getrandbits(32):08x}")
            break
