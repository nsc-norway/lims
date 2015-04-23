import os
import glob
import re
import subprocess
import win32api
import win32file
import win32event
import win32con

print_dir = "C:\\Printing"
libreoffice_path = "C:\\Program Files (x86)\\LibreOffice 4\\program\\soffice.exe"

# Define shortcuts for long printer names or names with hyphens here
printer_names = {
    'LABEL1': 'BMP51PGM511129101004-LABEL1'
    }

def get_new_jobs():
    for j in glob.glob(os.path.join(print_dir, "*.odt")):
        yield j

def do_print(filepath):
    filename = os.path.basename(filepath)
    printer_id = re.match("([A-Za-z0-9]+)-.*", filename)
    printer = printer_names.get(printer_id.group(1))
    if printer:
        print "Found a file", filepath, ", will print it."
        subprocess.check_call([libreoffice_path, '--pt', printer, filepath])
        os.remove(filepath)


def monitor_and_print():
    # Set up change notification
    change_handle = win32file.FindFirstChangeNotification(
            print_dir, 
            0,
            win32con.FILE_NOTIFY_CHANGE_FILE_NAME
            )

    for j in get_new_jobs():
        do_print(j)
        
    while True:
        result = win32event.WaitForSingleObject(change_handle, 500)
        if result == win32con.WAIT_OBJECT_0:
            for j in get_new_jobs():
                do_print(j)
            win32file.FindNextChangeNotification(change_handle)


monitor_and_print()


