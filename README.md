# QingcloudBWscaler
Qingcloud is a Chinese Iaas provider. They allow adjusting resources instantly and billed by seconds. This script monitors the instance's network bandwidth usage and adjust the bandwidth according to ensure quality of service at busy hour and avoid resource waste when idle
Required packages:
1. Zabbix-server for bandwidth usage monitoring, please refer to https://www.zabbix.com/documentation/3.4/manual/installation for installation instructions.

2. Python 2.7

3. Qingcloud Python SDK: Please refer to https://github.com/yunify/qingcloud-sdk-python for installation instructions.

4. MySQL server for historical data recording.

5. Python packages:
    5.1: requests for RESTful API access
    5.2: mysql-python for database access
Please refer to the main section of the code for the config paramters.
