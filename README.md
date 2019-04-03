# Prometheus SSH Exporter

This is a SSH Exporter for Prometheus that runs shell commands on remote servers.
It only supports results that are integer and it will try to convert to integer.

## Features:
  - Multithread running commands
  - Live changes to config file
  - Connect to remote server either with username/password or key authentication
  - Support for multiple ssh results with delimeter "|"
  - Run custom methods by adding additional methods on SSHConnection class
  - Continues running even if it gets an error result (check terminal)

## Config:
Default path of configuration is `ssh_settings.yml`
The default Prefix is `ssh_`
```yaml
port: 8001
scripts:
  - name: test_name
    description: 'Description of the Test'
    runmethod: run_shell
    cmd: ls /opt/ | wc -l
    credentials:
      user: username
      host: 192.168.1.5
      keyfile: 'C:\Prometheus\Exporters\SSH\privatekey.ppk'

  - name: test_name_2
    description: 'Description of the Test 2'
    runmethod: run_shell
    cmd: netstat -i | grep 'eth0' | awk '{print $4 "|" $8}'
    credentials:
      user: username
      pass: password
      host: 192.168.1.5
```

## Prometheus Config:
```yaml
scrape_configs:
  - job_name: 'ssh_exporter'
    scrape_timeout:  20s
    scrape_interval: 40s
    static_configs:
      - targets: ['localhost:8001']
```

## Important Info
This exported doesn't support filtering results on by URL Probe. Each call will run and return all results.