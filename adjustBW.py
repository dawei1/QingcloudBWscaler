import json
import time
import math
import requests
import MySQLdb
import datetime
import qingcloud.iaas
# Get bandwidth usage from zabbix server
# For zabbix API please refer to https://www.zabbix.com/documentation/3.4/manual/api
def getBW(shortduration, longduration, hostid, itemid1, itemid2, url, user, passwd):
	headers = {"Content-Type" : "application/json-rpc"};
	payload = {
		"jsonrpc": "2.0",
		"method": "user.login",
		"params": {
 			"user": user,
			"password": passwd
		},
		"id": 1,
	}
	r = requests.post(url, data=json.dumps(payload), headers=headers)
	response = r.json();
	auth = response['result'];
	time_till = datetime.datetime.now().strftime("%s");
	time_from = (datetime.datetime.now() - datetime.timedelta(seconds=shortduration)).strftime("%s");
	payload ={
		"jsonrpc": "2.0",
		"method": "history.get",
		"params": {
			"output": "extend", 
			"history": 3,
			"itemids": [itemid1,itemid2],
			"sortfield": "clock",
			"hostid": hostid,
			"sortorder": "DESC",
			"time_from": time_from,
			"time_till": time_till},
		"id": 1,
		"auth": auth
        }
	r = requests.post(url, data=json.dumps(payload), headers=headers)
	response = r.json();
	BW1 = 0;
	BW2 = 0;
	count1 = 0;
	count2 = 0;
	# Get max short term bandwidth usage, max(uplink, downlink), in Byte/second
	for data in response['result']:
		if(data["itemid"] == itemid1):
			count1 = count1+1;
			BW1 = BW1 + int(data["value"]);
		else:
			count2 = count2+1;
			BW2 = BW2 + int(data["value"]);
	# Return in bit/second
	ShortBW = 8*max([BW1/count1, BW2/count2]);
	time_from = (datetime.datetime.now() - datetime.timedelta(seconds=longduration)).strftime("%s");
	payload ={
		"jsonrpc": "2.0",
		"method": "history.get",
		"params": {
			"output": "extend",
			"history": 3,
			"itemids": [itemid1,itemid2],
			"sortfield": "clock",
			"hostid": hostid,
			"sortorder": "DESC",
			"time_from": time_from,
			"time_till": time_till},
		"id": 1,
		"auth": auth
	}
	r = requests.post(url, data=json.dumps(payload), headers=headers)
	response = r.json();
	BW1 = 0;
	BW2 = 0;
	count1 = 0;
	count2 = 0;
	# Get max long term bandwidth usage,  max(uplink, downlink), Byte/second 
	for data in response['result']:
		if(data["itemid"] == itemid1):
			count1 = count1+1;
			BW1 = BW1 + int(data["value"]);
		else:
			count2 = count2+1;
			BW2 = BW2 + int(data["value"]);
	#Return in bit/second
	LongBW = 8*max([BW1/count1, BW2/count2]); 
	return [LongBW, ShortBW];

# Get current bandwith limit of the cloud instance
# Please refer to QingCloud API at https://docs.qingcloud.com/api/
# Need to install QingCloud Python SDK at https://github.com/yunify/qingcloud-sdk-python
def getCloudBW(zone, access_key_id, secret_access_key, eipid):
	conn = qingcloud.iaas.connect_to_zone(zone,access_key_id,secret_access_key);
	# Default ot get only 1 eip, easy to extend to multiple eips
	eipinfo = conn.describe_eips([{'eips':eipid}]);
	#Return in bit/second
	BW = eipinfo['eip_set'][0]['bandwidth']*1024*1024;
	return BW;
# Set the new bandwidth limit for the cloud instance
# TargetBW is in Mbit/second
def setCloudBW(targetBW, zone, access_key_id, secret_access_key, eipid):
	conn = qingcloud.iaas.connect_to_zone(zone,access_key_id,secret_access_key);
	eipinfo = conn.change_eips_bandwidth([eipid], targetBW);
	return eipinfo;
# Get the target bandwidth based on the current long term 
def BWadjust(LongBW, ShortBW, BWlimint, BWlowLimit, BWlowThreshold, BWhighThreshold, factor, factor2, BWhighLimit):
	# Increase the bandwidth if the short term bandiwth is approaching the bandwidth limit
	if (ShortBW > BWlowThreshold*BWlimit):
		targetBW = int(math.ceil(ShortBW/factor/1024/1024));
	# Convervative decrement of the bandwidth limit, only happens when both short- and long-term bandwidth usage is below threshold
	elif(ShortBW < BWhighThreshold*BWlimit and LongBW < BWhighThreshold * BWlimit):
		targetBW = int(math.ceil(ShortBW*factor/1024/1024));
	# Or don't change the bandwidth limit
	else:
		targetBW = BWlimit/1024/1024;
	# If the target bandwidth limit is > 5Mbps, think twice.
	if(targetBW > 5):
		if (ShortBW > BWlowThreshold*BWlimit):
			targetBW = int(math.ceil(ShortBW/factor/factor2/1024/1024));
			if(targetBW < 5):
				targetBW = 5;
		elif(ShortBW < BWhighThreshold*BWlimit and LongBW < BWhighThreshold * BWlimit):
			targetBW = int(math.ceil(shortBW*factor/factor2/1024/1024));
		else:
                	targetBW = BWlimit/1024/1024;
	if(targetBW < BWlowLimit):
	        targetBW = BWlowLimit;
	if(targetBW > BWhighLimit):
		targetBW = BWhighLimit;
	return targetBW;

# Main program
# MySQL server to record every bandwidth changes, comment out if you don't need it.
sqlhost = '';
sqluser = '';
sqlpasswd = '';
sqldb = '';
sqlport = 3306;
connection = MySQLdb.connect(host=sqlhost, user=sqluser, passwd=sqlpasswd, db=sqldb, port=sqlport, use_unicode=True);
cursor = connection.cursor();
# Default schema is:
#       id: INT, PK, Auto incremnt, Unsigned, Not null, indexed
#       BWusage: INT, Unsigned, Not null,
#       BWtarget: INT, unsigned, not null,
#       time: datetime, not null,
#       message: text,
#       returenval: INT, not null
query = "INSERT INTO BWhistory (BWusage, BWtarget, time, message, returnval) VALUES (%s, %s, %s, %s, %s)";
# Zabbix server info
#Short term avg bandwidth usage, in second
shortduration = 5;
#Long term avg bandwidth suage, ins econd
longduration = 60;
#zabbix hostid
hostid = '';
#itmeid of the uplink bandwidth
itemid1 = '';
#itemid of the downlink bandwidth
itemid2 = '';
# url to access zabbix server API
url="http://zabbix_server_ip:port/zabbix/api_jsonrpc.php";
zabbixuser = '';
zabbixpasswd = '';
# Qingcloud API access keys, please request from your console
zone = '';
access_key_id = '';
secret_access_key = '';
# The id of the eip that you want to adjust bandwidth.
eipid = '';
# Bandwidth limit adjustment parameters.
# Lower limit of the target bandwidth
BWlowLimit = 1;
# The percentage that determines the current bandwidth limit is too low
BWlowThreshold = 0.65;
# The percentage that determines tht current bandwidth limit is too high
BWhighThreshold= 0.25;
# BW change factor
factor = 0.7;
# The BW price is significantly higher when > 5Mbps, this factor makes scaling action more conservative when target BW is > 5Mbps
factor2 = 1.3;
# High limit of the target bandwidth
BWhighLimit = 10;
# Run it every 7~10 seconds, 6 times a mintue.
# cron job can be used to schedule its execution
for count in range(6):
	[LongBW, ShortBW] = getBW(shortduration, longduration, hostid, itemid1, itemid2, url, zabbixuser, zabbixpasswd);
	BWlimit = getCloudBW(zone, access_key_id, secret_access_key, eipid);
	returnval = 0;
	returnmessage = "No need to adjust bandwidth";
	targetBW = BWadjust(LongBW, ShortBW, BWlimit, BWlowLimit, BWlowThreshold, BWhighThreshold, factor, factor2, BWhighLimit);
	if(targetBW*1024*1024 != BWlimit):
		eipinfo = setCloudBW(targetBW, zone, access_key_id, secret_access_key, eipid);
		returnval = eipinfo['ret_code'];
		if(returnval != 0):
			returnmessage = eipinfo['message'];
		else:
			returnmessage = "Bandwidth adjustment successfully";
	currenttime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S");
	cursor.execute(query, (ShortBW, targetBW*1024*1024, currenttime, returnmessage, returnval));
	if(count < 5):
		time.sleep(8);
cursor.close();
connection.commit();
connection.close();
