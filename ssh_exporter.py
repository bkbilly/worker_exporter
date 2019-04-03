#!/usr/bin/python

__author__ = "bkbilly"

from prometheus_client import start_http_server, Metric, REGISTRY
import yaml
import sys
import time
import paramiko
import threading

runforever = True


def graceful_exit(msg=''):
    print('------------------------')
    print(msg)
    print('---- I HAVE TO EXIT ----')
    global runforever
    runforever = False
    sys.exit()


def get_settings():
    config_file = "ssh_settings.yml"
    stream = open(config_file, "r")
    settings = yaml.load(stream, Loader=yaml.CLoader)
    return settings


class SSHConnection(object):
    def __init__(self, script):
        self.script = script
        self.ssh_host = self.script['credentials']['host']
        self.ssh_port = 22
        self.ssh_user = self.script['credentials']['user']
        self.ssh_pass = None
        self.ssh_keyfile = None

        if 'keyfile' in self.script['credentials']:
            self.ssh_keyfile = self.script['credentials']['keyfile']
        else:
            self.ssh_pass = self.script['credentials']['pass']
            if 'port' in self.script['credentials']:
                self.ssh_port = self.script['credentials']['port']

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.ssh_host, self.ssh_port, username=self.ssh_user, password=self.ssh_pass, key_filename=self.ssh_keyfile)

    def run_shell(self):
        stdin, stdout, stderr = self.ssh.exec_command(self.script['cmd'])
        stdout = stdout.read().decode("utf-8")
        results = []
        for result in stdout.split('|'):
            results.append(int(result))
        return results

    def run_mysql(self):
        cmd = 'echo "%s" | /usr/local/bin/dbgo %s | tail -n +5' % (self.script['query'], self.script['db'])
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        stdout = stdout.read().decode("utf-8")
        results = []
        for row in stdout.split('\n')[:-1]:
            results.append(int(row))
        return results


class MetricCollector(object):
    def __init__(self):
        self.settings = get_settings()
        self.metric_samples = []

    def collect(self):
        self.settings = get_settings()
        # Fetch the JSON
        print('---------------')
        self.metric_samples = []
        threads = []
        flag = 1
        for script in self.settings['scripts']:
            t = threading.Thread(target=self.ssh_result, args=(script,))
            threads.append(t)
            t.start()
            time.sleep(0.1)
        while (flag):
            time.sleep(0.5)
            flag = 0
            for t in threads:
                if t.isAlive():
                    flag = 1

        metric = Metric('ssh_exporter', 'SSH Exporter by bkbilly', 'summary')
        for metric_sample in self.metric_samples:
            metric.add_sample(metric_sample['name'], value=metric_sample['result'], labels={'num': metric_sample['num']})

        yield metric

    def ssh_result(self, script):
        try:
            myssh = SSHConnection(script)
            if hasattr(myssh, script['runmethod']):
                results = eval('myssh.%s()' % (script['runmethod']))
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


settings = get_settings()
start_http_server(settings['port'])
REGISTRY.register(MetricCollector())


while runforever:
    time.sleep(1)
