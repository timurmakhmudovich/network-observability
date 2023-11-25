import re
import os
import time
import pickle

import redis
import pynetbox

from apscheduler.schedulers.background import BackgroundScheduler


NETBOX_URL = os.getenv('NETBOX_URL')
NETBOX_TOKEN = os.getenv('NETBOX_TOKEN')

scheduler = BackgroundScheduler()
netbox_client = pynetbox.api(NETBOX_URL, NETBOX_TOKEN)
redis_client = redis.Redis(host='redis', port=6379, db=0)


@scheduler.scheduled_job('interval', hours=1)
def push_ips():
    """
    Cron function to send IP addresses information to Redis.
    Example of sent data:
    {
        '172.16.1.2': {
            'site': 'DC1',
            'hostname': 'dc1-server1'
        },
        ...
    }
    """
    ip_addresses = netbox_client.ipam.ip_addresses.all()
    ips_info = {}

    for ip_address in ip_addresses:
        ip = re.sub('/.*', '', ip_address.display)
        hostname = ip_address.assigned_object.device.display
        device = netbox_client.dcim.devices.get(name=hostname)
        site = device.site.display
        ips_info[ip] = {'site': site, 'hostname': hostname}

    redis_client.set('ips', pickle.dumps(ips_info))


@scheduler.scheduled_job('interval', hours=1)
def push_supernets():
    """
    Cron function to send prefixes information to Redis.
    Example of sent data:
    [
        {
            'prefix': '172.16.1.0/24', 
            'site': 'DC1'
        },
        ...
    ]
    """
    supernets = netbox_client.ipam.prefixes.filter(role='supernet')
    supernets_info = []

    for net in supernets:
        prefix = net.prefix
        site = net.site.display

        supernet_info = {
            'prefix': prefix,
            'site': site
        }

        supernets_info.append(supernet_info)

    supernets_info.append({'prefix': '0.0.0.0/0', 'site': 'INTERNET'})
    redis_client.set('supernets', pickle.dumps(supernets_info))


if __name__ == "__main__":
    push_ips()
    push_supernets()
    scheduler.start()

    while True:
        time.sleep(1)
