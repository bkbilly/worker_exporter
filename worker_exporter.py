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
from ssh2.session import Session
import socket
import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

class Worker(object):
    def __init__(self, script):
        self.script = script
        if hasattr(self.script, 'timeout'):
            self.timeout = int(self.script['timeout'])
        else:
            self.timeout = 2

    def soap_timed_result(self):
        start = time.time()
        client = Client(self.script['wsdl'])
        if hasattr(client.service, self.script['service']):
            client.service[self.script['service']](**self.script['inputs'])
        else:
            graceful_exit('Service %s not found' % (self.script['service']))
        end = time.time()
        yield end - start

    def run_onenetlogin(self):
        url = self.script['url']
        urllib_result = urllib.request.urlopen(url, timeout=self.timeout).read()
        soup = BeautifulSoup(urllib_result, 'html.parser')
        latestvalue = soup.find_all('table')[2].find_all('tr')[1].find_all('td')[3].get_text()

        for result in latestvalue.split('|'):
            yield float(result)

    def ssh_timed_result(self):
        start = time.time()
        ssh = self._get_ssh_old()
        stdin, stdout, stderr = ssh.exec_command(self.script['cmd'], timeout=self.timeout)
        ssh.close()
        end = time.time()
        yield end - start

    def run_shell_old(self):
        ssh = self._get_ssh_old()
        stdin, stdout, stderr = ssh.exec_command(self.script['cmd'], timeout=self.timeout)
        stdout = stdout.read().decode("utf-8")
        ssh.close()
        for result in stdout.split('|'):
            yield float(result)

    def run_mysql(self):
        ssh = self._get_ssh_old()
        cmd = 'echo "%s" | /usr/local/bin/dbgo %s | tail -n +5' % (self.script['query'], self.script['db'])
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=self.timeout)
        stdout = stdout.read().decode("utf-8")
        ssh.close()
        for row in stdout.split('\n')[:-1]:
            yield float(row)

    def run_shell(self):
        ssh = self._get_ssh()
        ssh.execute(self.script['cmd'])
        size, stdout = ssh.read()
        ssh.close()
        for row in stdout.decode("utf-8").split('|'):
            yield float(row)
        # print("Exit status: %s" % ssh.get_exit_status())

    def _get_ssh_old(self):
        ssh_host = self.script['credentials']['host']
        ssh_port = 22
        ssh_user = self.script['credentials']['user']
        ssh_pass = None
        ssh_keyfile = None

        if 'port' in self.script['credentials']:
            ssh_port = self.script['credentials']['port']
        if 'keyfile' in self.script['credentials']:
            ssh_keyfile = self.script['credentials']['keyfile']
        else:
            ssh_pass = self.script['credentials']['pass']

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_host, ssh_port, username=ssh_user, password=ssh_pass, key_filename=ssh_keyfile)
        return ssh

    def _get_ssh(self):
        ssh_host = self.script['credentials']['host']
        ssh_port = 22
        ssh_user = self.script['credentials']['user']
        ssh_pass = None
        ssh_keyfile = None

        if 'port' in self.script['credentials']:
            ssh_port = self.script['credentials']['port']
        if 'keyfile' in self.script['credentials']:
            if os.path.exists(self.script['credentials']['keyfile']):
                ssh_keyfile = self.script['credentials']['keyfile']
        else:
            ssh_pass = self.script['credentials']['pass']

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ssh_host, ssh_port))
        session = Session()
        session.handshake(sock)
        if ssh_keyfile is not None:
            session.userauth_publickey_fromfile(ssh_user, ssh_keyfile)
        else:
            session.userauth_password(ssh_user, ssh_pass)
        channel = session.open_session()
        return channel


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
                for num, result in enumerate(eval('myworker.%s()' % (script['runmethod']))):
                    print('%s {num=%s}: %s' % (script['name'], num, result))
                    self.metric_samples.append({
                        'name': 'worker_' + script['name'],
                        'result': result,
                        'num': str(num)
                    })
            else:
                graceful_exit('No such method exists...')
        except Exception as e:
            print('--------------> %s' % (script['name']))
            print(e)
            print('<---- END ERROR')


runforever = True
config_file = "settings.yml"
if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = input("enter filename:")

settings = get_settings()
start_http_server(settings['port'])
REGISTRY.register(MetricCollector())


while runforever:
    time.sleep(1)
