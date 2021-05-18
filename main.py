import os
import subprocess
from collections import Counter
from wsgiref.simple_server import make_server

from prometheus_client import make_wsgi_app, Gauge

host = os.uname()[1]
g_warnings = Gauge('metrics_log_warnings', 'Check presence of warn lines in metrics log',
                   ['host', 'level', 'class'])

def generate():
    try:
        proc1 = subprocess.Popen(['cat', 'metrics.log'], stdout=subprocess.PIPE)
        proc2 = subprocess.Popen(['grep', '-E', 'WARN|ERROR|FATAL'], stdin=proc1.stdout, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        proc3 = subprocess.Popen(['grep', '-v', "Overwriting existing descriptor file"], text=True, stdin=proc2.stdout,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc3.communicate()
        if err:
            g_warnings.labels(host, "Problem grepping log - {}".format(err)).set(1)
        else:
            list_of_errors = Counter([(x.split(' ')[2], x.split(' ')[3]) for x in out.split('\n') if x != ''])

            for c in list_of_errors:
                g_warnings.labels(host, c[0], c[1]).set(list_of_errors[c])

    except Exception as e:
        g_warnings.labels(host, "Problem running exporter - {}".format(e)).set(1)



metrics_app = make_wsgi_app()


def metrics_exporter(environ, start_fn):
    if environ['PATH_INFO'] == '/metrics':
        generate()
        return metrics_app(environ, start_fn)


httpd = make_server('', 8000, metrics_exporter)
httpd.serve_forever()
