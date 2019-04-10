#!/usr/bin/python

__author__ = "bkbilly"

from prometheus_client import start_http_server, Metric, REGISTRY
import yaml
import sys
import time
import paramiko
import threading
from bs4 import BeautifulSoup
import urllib
from zeep import Client


class Worker(object):
    def __init__(self, script):
        self.script = script
        self.timeout = 2

    def soap_timed_result(self):
        start = time.time()
        client = Client(self.script['wsdl'])
        if hasattr(client.service, self.script['service']):
            client.service[self.script['service']](**self.script['inputs'])
        else:
            graceful_exit('Service %s not found' % (self.script['service']))
        end = time.time()
        return [end - start]

    def run_onenetlogin(self):
        url = "https://grpal-wias125.vf-gr.internal.vodafone.com/vop/ListTextOneLogin.php"
        urllib_result = urllib.request.urlopen(url, timeout=self.timeout).read()
        soup = BeautifulSoup(urllib_result, 'html.parser')
        latestvalue = soup.find_all('table')[2].find_all('tr')[1].find_all('td')[3].get_text()

        results = []
        for result in latestvalue.split('|'):
            results.append(float(result))
        return results

    def _get_ssh(self):
        ssh_host = self.script['credentials']['host']
        ssh_port = 22
        ssh_user = self.script['credentials']['user']
        ssh_pass = None
        ssh_keyfile = None

        if 'keyfile' in self.script['credentials']:
            ssh_keyfile = self.script['credentials']['keyfile']
        else:
            ssh_pass = self.script['credentials']['pass']
            if 'port' in self.script['credentials']:
                ssh_port = self.script['credentials']['port']

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_host, ssh_port, username=ssh_user, password=ssh_pass, key_filename=ssh_keyfile)
        return ssh

    def run_shell(self):
        ssh = self._get_ssh()
        stdin, stdout, stderr = ssh.exec_command(self.script['cmd'], timeout=self.timeout)
        stdout = stdout.read().decode("utf-8")
        results = []
        for result in stdout.split('|'):
            results.append(float(result))
        ssh.close()
        return results

    def run_mysql(self):
        ssh = self._get_ssh()
        cmd = 'echo "%s" | /usr/local/bin/dbgo %s | tail -n +5' % (self.script['query'], self.script['db'])
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=self.timeout)
        stdout = stdout.read().decode("utf-8")
        results = []
        for row in stdout.split('\n')[:-1]:
            results.append(float(row))
        ssh.close()
        return results


def graceful_exit(msg=''):
    print('------------------------')
    print(msg)
    print('---- I HAVE TO EXIT ----')
    global runforever
    runforever = False
    sys.exit()


def get_settings():
    stream = open(config_file, "r")
    settings = yaml.load(stream, Loader=yaml.CLoader)
    return settings


class MetricCollector(object):
    def __init__(self):
        self.settings = get_settings()
        self.metric_samples = []

    def collect(self):
        start = time.time()
        self.settings = get_settings()
        # Fetch the JSON
        print('-----START-----')
        self.metric_samples = []
        threads = []
        flag = 1
        for script in self.settings['scripts']:
            t = threading.Thread(target=self.worker_result, args=(script,))
            threads.append(t)
            t.start()
            time.sleep(0.2)
        while (flag):
            time.sleep(0.5)
            flag = 0
            for t in threads:
                if t.isAlive():
                    flag = 1

        metric = Metric('worker_exporter', 'Worker Exporter by bkbilly', 'summary')
        for metric_sample in self.metric_samples:
            metric.add_sample(metric_sample['name'], value=metric_sample['result'], labels={'num': metric_sample['num']})
        end = time.time()
        print('Total RunTime =', end - start)
        print('-----END-----')

        yield metric

    def worker_result(self, script):
        try:
            myworker = Worker(script)
            if hasattr(myworker, script['runmethod']):
                results = eval('myworker.%s()' % (script['runmethod']))
                print(script['name'], results)
                for num, result in enumerate(results):
                    self.metric_samples.append({
                        'name': 'ssh_' + script['name'],
                        'result': result,
                        'num': str(num)
                    })
            else:
                graceful_exit('No such method exists...')
        except Exception as e:
            print('-------------->')
            print(e)
            print('<---- END ERROR')


runforever = True
config_file = "ssh_settings.yml"
if len(sys.argv) > 1:
    config_file = sys.argv[1]

settings = get_settings()
start_http_server(settings['port'])
REGISTRY.register(MetricCollector())


while runforever:
    time.sleep(1)
