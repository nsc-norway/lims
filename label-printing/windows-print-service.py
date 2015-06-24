import os
import glob
import re
import subprocess
import win32api
import win32file
import win32event
import win32con
import win32serviceutil
import win32service
import win32event
import servicemanager

# Can be installed as a service by running the following in an administrator shell:
# python windows-print-service.py install

# Then go into the service manager and set it to start automatically, and run as the
# Local System user.

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


class AppServerSvc (win32serviceutil.ServiceFramework):
    _svc_name_ = "LabelPrintingService"
    _svc_display_name_ = "Label printing service"

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)
        self.hWaitStop = win32event.CreateEvent(None,0,0,None)
        self.stop = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop = True
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_,''))
        self.monitor_and_print()

    def monitor_and_print(self):
        # Set up change notification
        change_handle = win32file.FindFirstChangeNotification(
                print_dir, 
                0,
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME
                )

        for j in get_new_jobs():
            do_print(j)
            
        while not self.stop:
            result = win32event.WaitForMultipleObjects([change_handle, self.hWaitStop], False, 500)
            if result == win32con.WAIT_OBJECT_0:
                for j in get_new_jobs():
                    do_print(j)
                win32file.FindNextChangeNotification(change_handle)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AppServerSvc)
