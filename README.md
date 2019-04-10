# Prometheus Worker Exporter

This is an Exporter for Prometheus that runs any method that is needed, like shell commands, soap requests etc...
It only supports results that are integer and it will try to convert to that.

## Features:
  - Multithread running commands
  - Live changes to config file
  - Multiple configurations as input
  - Connect to remote server either with username/password or key authentication
  - Support for multiple results with delimeter "|"
  - Run custom methods by adding additional methods on Worker class
  - Continues running even if it gets an error result (check terminal)

## Config:
Default path of configuration is `settings.yml`
The default Prefix is `worker_`
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
      keyfile: 'privatekey.ppk'

  - name: soap_test
    description: 'Show Telephone Numbers'
    runmethod: soap_timed_result
    wsdl: http://192.168.2.50:7777/MySOAPTest?WSDL
    service: shownumber
    inputs:
      cli: 21028182839
```

## Prometheus Config:
```yaml
scrape_configs:
  - job_name: 'worker_exporter'
    scrape_timeout:  30s
    scrape_interval: 40s
    static_configs:
      - targets: ['localhost:8001']
```

## Important Info
This exported doesn't support filtering results on by URL Probe. Each call will run and return all results.