# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  or in the "license" file accompanying this file. This file is distributed
#  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#  express or implied. See the License for the specific language governing
#  permissions and limitations under the License.

# pip3 install requests nvidia-ml-py3 boto3

import boto3
import requests
from pynvml import *
from datetime import datetime
from time import sleep

### CHOOSE REGION ####
EC2_REGION = 'us-east-1'

###CHOOSE NAMESPACE PARMETERS HERE###
my_NameSpace = 'OmnisciGPU'

### CHOOSE PUSH INTERVAL ####
sleep_interval = 10

### CHOOSE STORAGE RESOLUTION (BETWEEN 1-60) ####
store_reso = 60

#Instance information
BASE_URL = 'http://169.254.169.254/latest/meta-data/'
INSTANCE_ID = requests.get(BASE_URL + 'instance-id').text
IMAGE_ID = requests.get(BASE_URL + 'ami-id').text
INSTANCE_TYPE = requests.get(BASE_URL + 'instance-type').text
INSTANCE_AZ = requests.get(BASE_URL + 'placement/availability-zone').text
EC2_REGION = INSTANCE_AZ[:-1]

TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H')
TMP_FILE = '/tmp/GPU_TEMP'
TMP_FILE_SAVED = TMP_FILE + TIMESTAMP

# Create CloudWatch client
cloudwatch = boto3.client('cloudwatch', region_name=EC2_REGION)


# Flag to push to CloudWatch
PUSH_TO_CW = True

def getPowerDraw(handle):
    try:
        powDraw = nvmlDeviceGetPowerUsage(handle) / 1000.0
        powDrawStr = '%.2f' % powDraw
    except NVMLError as err:
        powDrawStr = handleError(err)
        PUSH_TO_CW = False
    return powDrawStr

def getTemp(handle):
    try:
        temp = str(nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU))
    except NVMLError as err:
        temp = handleError(err)
        PUSH_TO_CW = False
    return temp

def getMemoryUtilization(handle):
    try:
        info = nvmlDeviceGetMemoryInfo(handle)
        free = info.free
        total = info.total
        used = info.used
        mem_util = info.used/info.total * 100
    except NVMLError as err:
        error = handleError(err)
        gpu_util = error
        mem_util = error
        PUSH_TO_CW = False
    return free, total, used, mem_util

def logResults(i, free, total, used, mem_util, powDrawStr, temp):
    if (PUSH_TO_CW):
        print("push to cw")
        MY_DIMENSIONS=[
                    {
                        'Name': 'InstanceId',
                        'Value': INSTANCE_ID
                    },
                    {
                        'Name': 'ImageId',
                        'Value': IMAGE_ID
                    },
                    {
                        'Name': 'InstanceType',
                        'Value': INSTANCE_TYPE
                    },
                    {
                        'Name': 'GPUNumber',
                        'Value': str(i)
                    }
                ]
        cloudwatch.put_metric_data(
            MetricData=[
                {
                    'MetricName': 'Total Memory',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'Bytes',
                    'StorageResolution': store_reso,
                    'Value': total
                },
                {
                    'MetricName': 'Used Memory',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'Bytes',
                    'StorageResolution': store_reso,
                    'Value': used
                },
                {
                    'MetricName': 'Free Memory',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'Bytes',
                    'StorageResolution': store_reso,
                    'Value': free
                },
                {
                    'MetricName': 'Memory Usage',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'Percent',
                    'StorageResolution': store_reso,
                    'Value': mem_util
                },
                {
                    'MetricName': 'Power Usage (Watts)',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'None',
                    'StorageResolution': store_reso,
                    'Value': float(powDrawStr)
                },
                {
                    'MetricName': 'Temperature (C)',
                    'Dimensions': MY_DIMENSIONS,
                    'Unit': 'None',
                    'StorageResolution': store_reso,
                    'Value': int(temp)
                },
        ],
            Namespace=my_NameSpace
        )


nvmlInit()
deviceCount = nvmlDeviceGetCount()

def main():
    try:
        PUSH_TO_CW = True
        # Find the metrics for each GPU on instance
        for i in range(deviceCount):
            handle = nvmlDeviceGetHandleByIndex(i)

            powDrawStr = getPowerDraw(handle)
            temp = getTemp(handle)
            free, total, used, mem_util = getMemoryUtilization(handle)
            logResults(i, free, total, used, mem_util, powDrawStr, temp)
            print(free,total,used,mem_util)
    finally:
        nvmlShutdown()

if __name__=='__main__':
    main()

