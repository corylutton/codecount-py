#!/usr/bin/env python3
###############################################################################
# Copyright 2013 Cory Lutton                                                  #
#                                                                             #
# Licensed under the Apache License, Version 2.0 (the "License");             #
# you may not use this file except in compliance with the License.            #
# You may obtain a copy of the License at                                     #
#                                                                             #
#    http://www.apache.org/licenses/LICENSE-2.0                               #
#                                                                             #
# Unless required by applicable law or agreed to in writing, software         #
# distributed under the License is distributed on an "AS IS" BASIS,           #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    #
# See the License for the specific language governing permissions and         #
# limitations under the License.                                              #
###############################################################################
"""
Count the lines in text type files recursively though a directory
based on the extension of the file.
"""
import os
import sys
import time
import json
import logging
import argparse
import hashlib
import xml.etree.ElementTree as ET

__version__ = "0.1"


class CodeCounter:
    """Main Code Counter Class"""

    ignoredirs = (".hg", ".bzr", ".svn", ".git", ".idea", "__pycache__")
    langs = {
        "C": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".c"],
        },
        "C++": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".cpp"],
        },
        "C#": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".cs"],
        },
        "C Header": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".h"],
        },
        "CSS": {
            "bcomm": {"/*": "*/"},
            "comment": [],
            "endcode": [],
            "ext": [".css"],
        },
        "Cython": {
            "bcomm": {},
            "comment": ["#"],
            "endcode": [],
            "ext": [".pyx"],
        },
        "Go": {
            "bcomm": {},
            "comment": ["//"],
            "endcode": [],
            "ext": [".go"],
        },
        "HTML": {
            "bcomm": {"<!--": "-->"},
            "comment": [],
            "endcode": [],
            "ext": [".html", ".htm", ".jinja"],
        },
        "IBM Macro": {
            "bcomm": {"/*": "*/"},
            "comment": ["'"],
            "endcode": [],
            "ext": [".mac"],
        },
        "Java": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".java"],
        },
        "Javascript": {
            "bcomm": {"/*": "*/"},
            "comment": ["//"],
            "endcode": [],
            "ext": [".js"],
        },
        "Perl": {
            "bcomm": {},
            "comment": ["//", "#"],
            "endcode": ["__END__"],
            "ext": [".pl"],
        },
        "PHP": {
            "bcomm": {"/*": "*/"},
            "comment": ["//", "#"],
            "endcode": [],
            "ext": [".php"],
        },
        "Python": {
            "bcomm": {},
            "comment": ["#"],
            "endcode": [],
            "ext": [".py", ".pyw"],
        },
        "RPG": {
            "bcomm": {},
            "comment": [
                "*",
                "*",
                "C*",
                "c*",
                "D*",
                "d*",
                "F*",
                "f*",
                "H*",
                "h*",
            ],
            "endcode": [],
            "ext": [".rpgle", ".sqlrpgle"],
        },
        "Ruby": {
            "bcomm": {},
            "comment": ["#"],
            "endcode": ["__END__"],
            "ext": [".rb"],
        },
        "SQL": {
            "bcomm": {},
            "comment": [],
            "endcode": [],
            "ext": [".sql"],
        },
        "Text": {
            "bcomm": {},
            "comment": [],
            "endcode": [],
            "ext": [".txt"],
        },
        "VB": {
            "bcomm": {"/*": "*/"},
            "comment": ["'"],
            "endcode": [],
            "ext": [".vb", ".mac", ".frm", ".bas"],
        },
        "XML": {
            "bcomm": {"<!--": "-->"},
            "comment": [],
            "endcode": [],
            "ext": [".xml", ".csproj"],
        },
        "Yaml": {
            "bcomm": {},
            "comment": ["#"],
            "endcode": [],
            "ext": [".yaml"],
        },
    }

    def __init__(self):
        self.filelist = []
        self.tfiles = 0
        self.tlines = 0
        self.tcode = 0
        self.tcomments = 0
        self.tblanks = 0
        self.args = None

    def run(self):
        """Performs a code count"""
        self.commandline()
        starttime = time.time()

        if self.args.debug:
            logging.basicConfig(level=logging.DEBUG)

        self.listfiles()

        self.output()

        for filename in self.filelist:
            self.scanfile(filename)

        if not self.args.include:
            self.remove_duplicates()

        for filename in self.filelist:
            if filename.lines > 0:
                self.tfiles += 1

            self.tlines += filename.lines
            self.tcode += filename.code
            self.tcomments += filename.comments
            self.tblanks += filename.blanks

        assert self.tlines - self.tcode - self.tcomments - self.tblanks == 0

        self.report()

        if self.args.time:
            print(
                "Runtime: {} seconds".format(
                    str(round(time.time() - starttime, 3))
                )
            )

    # -----------------------------------------------------------------------------
    #   Processing methods
    # -----------------------------------------------------------------------------
    def commandline(self):
        """Parse the command line arguments"""
        parser = argparse.ArgumentParser(description="A Source Code Counter")

        # Positional
        parser.add_argument(
            "path",
            nargs="?",
            default=".",
            help="Provide a file path to count the code",
        )

        # Output options
        outgroup = parser.add_mutually_exclusive_group()

        outgroup.add_argument(
            "-f",
            "--byfile",
            action="store_true",
            default=True,
            help="Totals for each file - Default",
        )

        outgroup.add_argument(
            "-g",
            "--bygroup",
            action="store_true",
            default=False,
            help="Totals for each directory",
        )

        outgroup.add_argument(
            "-l",
            "--bylang",
            action="store_true",
            help="Totals for each language",
        )

        outgroup.add_argument(
            "-o",
            "--output-languages",
            action="store_true",
            help="Dump the known language file",
        )

        # General Options
        parser.add_argument(
            "-t",
            "--time",
            action="store_true",
            default=True,
            help="Print the runtime at completion",
        )

        parser.add_argument(
            "-d", "--debug", action="store_true", help="Turn on debug output"
        )

        parser.add_argument(
            "-i",
            "--include",
            action="store_true",
            help="Include duplicate files",
        )

        parser.add_argument(
            "-m",
            "--markup",
            choices=["xml", "json", "yaml"],
            help="Produce output in markup format",
        )

        self.args = parser.parse_args()

    def listfiles(self):
        """Get the list of files to check."""
        if os.path.isdir(self.args.path):
            logging.info("Path walked: %s", self.args.path)
            self.walk(self.args.path)
        else:
            root, filename = os.path.split(self.args.path)
            if os.path.isfile(root + "/" + filename):
                self.filelist.append(Filename(self.args.path, root, filename))

    def walk(self, path):
        """Walk the path excluding certain known directories"""
        for root, folders, files in os.walk(path):

            # Must go from ignoredirs
            for folder in self.ignoredirs:
                if folder in folders:
                    logging.info("Skipping Folder: %s", folder)
                    folders.remove(folder)

            # Append the file info
            for filename in files:
                if os.path.isfile(root + "/" + filename):
                    self.filelist.append(Filename(path, root, filename))

    def scanfile(self, filename):
        """The heart of the codecounter, Scans a file to identify
        and collect the metrics based on the classification."""
        strblock = None
        endblock = None
        inblock = False
        endcode = False
        sha256 = hashlib.sha256()

        if filename.size == 0:
            logging.info("Skipping File  : " + filename.name)
            return

        # Identify language
        for l in self.langs:
            if filename.extension in self.langs[l]["ext"]:
                filename.lang = l
                break

        # Unknown files don't need processed
        if filename.lang is None:
            logging.info("Skipping File  : " + filename.name)
            return

        # Using the with file opening in order to ensure no GC issues.
        with open(
            os.path.join(filename.path, filename.name),
            encoding="utf-8",
            errors="ignore",
        ) as fp:

            for line in fp:
                sha256.update(line.encode("utf-8"))
                filename.lines += 1
                line = line.strip()
                identified = False

                if line == "":
                    logging.info(" blak  " + str(filename.lines))
                    filename.blanks += 1
                    continue

                if endcode:
                    filename.comments += 1
                    continue

                # Check to see if it is a block or was an opening block
                # ex1 = "/*  */ if x;"          = Code, not inblock
                # ex2 = "*/ if x; /*"           = Code, inblock
                # ex3 = " if x; /*"             = Code, inblock
                # ex4 = "/*  */ if x; /* */ .." = Code, not inblock
                # ex4 = "*/"                    = Comment, not inblock
                # ex5 = "/* */"                 = Comment, not inblock
                # ex6 = "/*"                    = Comment, inblock
                # Two scenarios,
                # 1 - comments removed, code remains
                # 2 - Comments removed but block is open
                if not inblock:
                    for token in self.langs[filename.lang]["bcomm"]:
                        strblock = token
                        endblock = self.langs[filename.lang]["bcomm"][token]

                        while token in line:
                            spos = line.find(strblock)
                            epos = line.find(endblock, spos)

                            # TODO: Temporary fix so looping stops
                            if epos > 0:
                                epos += len(endblock)
                            else:
                                break

                            # If a block has started then check for an exit
                            if endblock in line:
                                line = line.replace(line[spos:epos], "", 1)
                            else:
                                line = line.replace(line[spos:], "", 1)
                                inblock = True  # left open
                else:
                    # Continue until the block ends... when left open
                    if endblock in line:
                        inblock = False  # End the block
                        line = line.replace(
                            line[: line.find(endblock) + len(endblock)], ""
                        ).strip()
                    else:
                        line = ""

                # From the block but no hidden code made it out the back....
                if line is "":
                    logging.info(" bloc  " + str(filename.lines) + line)
                    filename.comments += 1
                    continue

                # Check line comment designators
                for token in self.langs[filename.lang]["comment"]:
                    if line.startswith(token):
                        logging.info(" line  " + str(filename.lines) + line)
                        filename.comments += 1
                        identified = True
                        break

                if identified:
                    continue

                # If not a blank or comment it must be code
                logging.info(" code  " + str(filename.lines) + line)
                filename.code += 1

                # Check for the ending of code statements
                for end in self.langs[filename.lang]["endcode"]:
                    if line == end:
                        endcode = True

        # Store the hash of this file for comparison to others
        logging.info(
            "Total  "
            + " "
            + str(filename.blanks)
            + " "
            + str(filename.comments)
            + " "
            + str(filename.code)
        )

        filename.sha256 = sha256.digest()

    # -----------------------------------------------------------------------------
    #   Reporting Methods
    # -----------------------------------------------------------------------------
    def report(self):
        """Produce the report."""
        if self.args.bylang:
            self.report_lang()
        elif self.args.bygroup:
            self.report_dir()
        elif self.args.byfile:
            self.report_file()

    def remove_duplicates(self):
        """Remove duplicate files from the files list"""
        unique = {}
        uniquelist = []

        for filename in self.filelist:
            if filename.sha256 not in unique:
                unique[filename.sha256] = filename

        for u in unique:
            uniquelist.append(unique[u])

        self.filelist = uniquelist

    def report_header(self, reporttype):
        """Return the header for a report"""
        return (
            "Codecount - v "
            + __version__
            + "\n"
            + "-" * 79
            + "\n"
            + "{:<29}".format(reporttype)
            + "{:>10}".format("Files")
            + "{:>10}".format("Blank")
            + "{:>10}".format("Comment")
            + "{:>10}".format("Code")
            + "{:>10}".format("Lines")
            + "\n"
            + "-" * 79
        )

    def report_detail(self, text, files, blanks, comments, code, lines):
        """Return a detail line."""
        return (
            "{:<29}".format(text)
            + "{:>10}".format(files)
            + "{:>10}".format(blanks)
            + "{:>10}".format(comments)
            + "{:>10}".format(code)
            + "{:>10}".format(lines)
        )

    def report_summary(self):
        """Return the summary"""
        return (
            "-" * 79
            + "\n"
            + "{:<29}".format("Totals")
            + "{:>10}".format(self.tfiles)
            + "{:>10}".format(self.tblanks)
            + "{:>10}".format(self.tcomments)
            + "{:>10}".format(self.tcode)
            + "{:>10}".format(self.tlines)
            + "\n"
            + "-" * 79
        )

    def report_file(self):
        """Run a report by file"""

        print(self.report_header("By File"))

        for filename in sorted(
            self.filelist, key=lambda filename: filename.code, reverse=True
        ):

            if filename.lang is None:
                continue

            print(
                self.report_detail(
                    filename.shortname,
                    1,
                    filename.blanks,
                    filename.comments,
                    filename.code,
                    filename.lines,
                )
            )

        print(self.report_summary())

    def report_dir(self):
        """Run a report by directory"""

        print(self.report_header("By Directory"))

        # Subtotal by directory
        total = {
            "dir": None,
            "blank": 0,
            "comment": 0,
            "file": 0,
            "code": 0,
            "line": 0,
        }

        for filename in sorted(
            self.filelist, key=lambda filename: str(filename.shortpath)
        ):

            if filename.shortpath is None:
                continue

            if filename.shortpath == total["dir"]:
                total["blank"] += filename.blanks
                total["comment"] += filename.comments
                total["file"] += 1
                total["code"] += filename.code
                total["line"] += filename.lines
            else:
                # Print collected data before resetting.
                if total["dir"]:
                    print(
                        self.report_detail(
                            "",
                            total["file"],
                            total["blank"],
                            total["comment"],
                            total["code"],
                            total["line"],
                        )
                    )
                    print("-" * 79)

                total["dir"] = filename.shortpath
                total["blank"] = filename.blanks
                total["comment"] = filename.comments
                total["file"] = 1
                total["code"] = filename.code
                total["line"] = filename.lines
                print("{:<78}".format(total["dir"]))

        # Print the last
        if total["dir"]:
            print(
                self.report_detail(
                    "",
                    total["file"],
                    total["blank"],
                    total["comment"],
                    total["code"],
                    total["line"],
                )
            )

        print(self.report_summary())

    def report_lang(self):
        """Run a report by language"""

        print(self.report_header("By Language"))

        # Subtotal by language
        total = {
            "lang": None,
            "blank": 0,
            "comment": 0,
            "file": 0,
            "code": 0,
            "line": 0,
        }
        for filename in sorted(
            self.filelist, key=lambda filename: str(filename.lang)
        ):

            if filename.lang is None:
                continue

            if filename.lang == total["lang"]:
                total["blank"] += filename.blanks
                total["comment"] += filename.comments
                total["file"] += 1
                total["code"] += filename.code
                total["line"] += filename.lines
            else:
                # Print collected data before resetting.
                if total["lang"]:
                    print(
                        self.report_detail(
                            total["lang"],
                            total["file"],
                            total["blank"],
                            total["comment"],
                            total["code"],
                            total["line"],
                        )
                    )

                total["lang"] = filename.lang
                total["blank"] = filename.blanks
                total["comment"] = filename.comments
                total["file"] = 1
                total["code"] = filename.code
                total["line"] = filename.lines

        # Print the last.
        if total["lang"]:
            print(
                self.report_detail(
                    total["lang"],
                    total["file"],
                    total["blank"],
                    total["comment"],
                    total["code"],
                    total["line"],
                )
            )

        print(self.report_summary())

    # -----------------------------------------------------------------------------
    #   Other Output Methods
    # -----------------------------------------------------------------------------
    def output(self):
        """Output rather than report."""
        if self.args.output_languages:
            self.output_json_langs()
            sys.exit("File languages.json created.")
            self.output_xml_langs()
            sys.exit("File languages.xml created.")

    def output_json_langs(self):
        """Output languages as a JSON file."""
        outputfile = open("languages.json", "w")
        json.dump(self.langs, outputfile, indent=4, sort_keys=True)
        outputfile.close()

    def output_xml_langs(self):
        """Output languages as a JSON file."""
        outputfile = open("languages.xml", "w", encoding="utf-8")
        root = ET.Element("root")
        child = ET.SubElement(root, "child")
        child.attrib["name"] = "Charlie"
        tree = ET.ElementTree(root)
        tree.write(outputfile, encoding="unicode")
        outputfile.close()


# -----------------------------------------------------------------------------
#   Helpers
# -----------------------------------------------------------------------------
class Filename:
    """Setup a filename to collect the info"""

    def __init__(self, argpath, path, filename):
        self.path = path
        self.name = filename
        self.extension = os.path.splitext(filename)[1].lower()
        self.lang = None
        self.lines = 0
        self.comments = 0
        self.blanks = 0
        self.code = 0
        self.size = os.stat(os.path.join(path, filename)).st_size
        self.sha256 = None

        self.shortpath = "." + path[len(argpath) : len(argpath) + 78].strip()

        if len(filename) > 30:
            self.shortname = filename[:20].strip() + "~" + self.extension
        else:
            self.shortname = filename


# Run the main routine as the starting point
if __name__ == "__main__":
    cc = CodeCounter()
    cc.run()
