import os
import subprocess
from collections import Counter
from collections import defaultdict
from wsgiref.simple_server import make_server

from prometheus_client import make_wsgi_app, Gauge

host = os.uname()[1]
g_warnings = Gauge('metrics_log_warnings', 'Check presence of warn lines in metrics log',
                   ['host', 'script_name_pattern'])
g_totals = Gauge('metrics_log_total', 'Check presence of warn, error and fatal lines in metrics log',
                 ['host', 'script_name_pattern'])


def generate():
    try:
        proc1 = subprocess.Popen(['cat', 'metrics.log'], stdout=subprocess.PIPE)
        proc2 = subprocess.Popen(['grep', '-E', 'WARN|ERROR|FATAL'], stdin=proc1.stdout, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        proc3 = subprocess.Popen(['grep', '-v', "Overwriting existing descriptor file"], text=True, stdin=proc2.stdout,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc3.communicate()
        if err:
            g_warnings.labels(host, "Problems grepping log - {}".format(err)).set(1)
        else:
            list_of_errors = Counter([(x.split(' ')[2], x.split(' ')[3]) for x in out.split('\n') if x != ''])
            total_warnings = sum(list_of_errors[x] for x in list_of_errors if x[0] == 'WARN')
            total_errors = sum(list_of_errors[x] for x in list_of_errors if x[0] == 'ERROR')
            total_fatal = sum(list_of_errors[x] for x in list_of_errors if x[0] == 'FATAL')

            better_descriptions = defaultdict(str)

            for line in reversed(out.split('\n')):
                for c in list_of_errors:
                    if c[0] in line and c[1] in line:
                        better_descriptions[c] = line.split(c[1])[-1]
                        break
            for c in list_of_errors:
                g_warnings.labels(host, "{} - {}".format(c[1], better_descriptions[c])).set(list_of_errors[c])

            g_totals.labels(host, 'Total Warnings').set(total_warnings)
            g_totals.labels(host, 'Total Errors').set(total_errors)
            g_totals.labels(host, 'Total Fatal').set(total_fatal)

    except Exception as e:
        g_warnings.labels(host, "Problems grepping log - {}".format(e)).set(1)
        g_totals.labels(host, "Problems grepping log - {}".format(e)).set(1)


metrics_app = make_wsgi_app()


def metrics_exporter(environ, start_fn):
    if environ['PATH_INFO'] == '/metrics':
        generate()
        return metrics_app(environ, start_fn)


httpd = make_server('', 8000, metrics_exporter)
httpd.serve_forever()
