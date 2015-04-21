import os

from flask import Flask, request
from appy import pod
import tempfile

app = Flask(__name__)

#template_dir = "C:\\Users\\admin\\Desktop"
template_dir = "/Users/paalmbj/Documents"


label_template = {
        'tube': 'tube.odt',
        'box': 'box.odt'
        }

@app.route('/print/<labeltype>', methods=['POST'])
def print_label(labeltype):
    template_path = os.path.join(template_dir, label_template[labeltype])
    temp = tempfile.NamedTemporaryFile(suffix=".odt", delete=False)
    temp.close()
    try:
        renderer = pod.Renderer(template_path, request.post, temp.name)
        renderer.run()
        
    finally:
        os.remove(temp.name)
 

