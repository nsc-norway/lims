import os

import tempfile
import win32api
import win32print

from flask import Flask, request
from appy import pod
app = Flask(__name__)

#template_dir = "C:\\Users\\admin\\Desktop"
template_dir = "/Users/paalmbj/Documents"


label_template = {
        'tube': 'tube.odt',
        'box': 'box.odt'
        }
label_printer = {
        'tube': 'LABEL1',
        'box': 'LABEL2'
        }

use_printer = "LABEL1"

@app.route('/print/<labeltype>', methods=['POST'])
def print_label(labeltype):
    template_path = os.path.join(template_dir, label_template[labeltype])
    temp = tempfile.NamedTemporaryFile(suffix=".odt", delete=False)
    temp.close()
    try:
        renderer = pod.Renderer(template_path, request.post, temp.name)
        renderer.run()
        
        win32api.ShellExecute(
                0, "print", temp.name,
                '/d:"%s"' % label_printer[labeltype],
                ".", 0)
    finally:
        os.remove(temp.name)
 

