#!/bin/env python

# "Frozen in Time"
# Script to replace symlink with current version from git


# Normally, the files here under processtype/ are symlinks to the current version of
# scripts. When there's a new version of a processtype, we may want to keep the old
# scripts going for the old version of the processtype. So this script replaces links
# in the old # processtype's dir with the actual contents of the file. Before this
# is done, the current (old) processtype's dir is copied to a dir for the new processtype,
# so the new dir will contain links and not the file content.

# Specify the old process type dir to replace on the command line, and this script 
# will prompt for the new version number, and which files to replace with content.


# Caveat: This script doesn't work well if multiple older versions are in use.
# If you for instance freeze version 4.2, but 4.1 is also in use, then you may
# end up that the content of 4.1 are not actually frozen.

import os
import sys
import re
import glob
import subprocess

repo_base_dir = os.path.join(os.path.dirname(__file__), "..")

try:
    source = sys.argv[1].rstrip("/")
except IndexError:
    print("Use: {0} EXISTING_PROCESS_DIR".format(sys.argv[0]))
    sys.exit(1)

try:
    old_version = re.search(r"\d+\.\d+$", source).group(0)
    s_major, _, s_minor = old_version.partition(".")
    major, minor = int(s_major), int(s_minor)
except AttributeError:
    old_version = ""
    major, minor = 0, 0
except Exception as e:
    print(" > Error: {0}".format(e))
    sys.exit(1)

minor += 1
answer = raw_input("New version [{0}.{1}]: ".format(major, minor))
if answer:
    new_version = answer
else:
    new_version = "{0}.{1}".format(major, minor)

# First create a new dir by copying the old one
new_dir = re.sub(old_version + "$", new_version, source)
subprocess.call(['rsync', '-rl', source + "/", new_dir + "/"])

# Overwrite the file in the old dir
for f in glob.glob(os.path.join(source, "*")):
    if not f.endswith("genologics"):
        ans = raw_input("Freeze content of {0}? [y]: ".format(f))
        if ans.lower() == "y" or ans.lower() == "yes" or ans == "":
            link_dest = os.path.relpath(os.path.realpath(f), repo_base_dir)
            os.unlink(f)
            subprocess.call(['git show HEAD:{0} > {1}'.format(link_dest, f)], shell=True)

