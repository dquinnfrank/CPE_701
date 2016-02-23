# This contains general utility functions

import os

# Enforces file path
def enforce_path(path):
    try:
	os.makedirs(path)
    except OSError as exc: # Python >2.5
	if exc.errno == errno.EEXIST and os.path.isdir(path):
	    pass
	else: raise
