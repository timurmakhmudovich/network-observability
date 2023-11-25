import json
import time
import pickle
import ipaddress

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait

from redis import Redis
from kafka import KafkaConsumer
from clickhouse_driver import Client
from pandas import DataFrame
from apscheduler.schedulers.background import BackgroundScheduler


scheduler = BackgroundScheduler()
data_for_ch = []


@scheduler.scheduled_job('interval', minutes=30)
def get_data_from_redis():
    """
    Cron function for getting and updating IPAM data from Redis for enrichment.
    Example:
    supernets == [
        {'prefix': '172.16.0.0/16', 'site': 'DC1'},
        {'prefix': '172.17.0.0/16', 'site': 'DC2'},
        ...
    ]
    ips == {
        '10.28.126.13': {'site': 'DC2', 'hostname': 'dc2-leaf2'}, 
        '10.28.126.17': {'site': 'DC2', 'hostname': 'dc2-leaf1'}, 
        ...
    }
    """
    global ips
    global supernets

    redis_client = Redis(host='redis', port=6379, db=0)
    supernets = pickle.loads(redis_client.get('supernets'))
    ips = pickle.loads(redis_client.get('ips'))

def get_ip_info(ip: str):
    """
    Function for getting hostname and site info for given IP
    :param: ip - str - IP address of a host
    :return: tuple - (hostname, site) pair for IP address
    """
    if ip in ips.keys():
        return ips[ip]['hostname'], ips[ip]['site']
    else:
        hostname = 'Unknown'
        for supernet in supernets:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(supernet['prefix']):
                site = supernet['site']
                return hostname, site

def enrich(msg: dict):
    """
    Function for adding enriched data to the list data_for_ch
    :param: msg - dict - data recieved from Kafka
    Example:
    {
        'event_type': 'purge', 
        'peer_ip_src': '10.28.126.17', 
        'iface_in': 3,
        ...
    }
    """
    agent_ip = msg['peer_ip_src']
    dc = ips[agent_ip]['site']
    agent_name = ips[agent_ip]['hostname']

    src_hostname, src_site = get_ip_info(msg['ip_src'])
    dst_hostname, dst_site = get_ip_info(msg['ip_dst'])

    record = {
        'timestamp': msg['stamp_updated'],
        'agent_ip': agent_ip,
        'in_iface': msg['iface_in'],
        'src_ip': msg['ip_src'],
        'dst_ip': msg['ip_dst'],
        'proto': msg['ip_proto'],
        'src_port': msg['port_src'],
        'dst_port': msg['port_dst'],
        'packets': msg['packets'],
        'bytes': msg['packets'],
        'src_hostname': src_hostname,
        'src_site': src_site,
        'dst_hostname': dst_hostname,
        'dst_site': dst_site,
        'dc': dc,
        'agent_name': agent_name
    }

    data_for_ch.append(record)

def ch_insert():
    """
    Function for inserting enriched data into ClickHouse table
    """
    global data_for_ch

    ch_client = Client('clickhouse-server', settings={'use_numpy': True})
    columns = ['timestamp', 'agent_ip', 'in_iface', 'src_ip', 'dst_ip', 'proto', 'src_port', 'dst_port',
               'packets', 'bytes', 'src_hostname', 'src_site', 'dst_hostname', 'dst_site', 'dc', 'agent_name']
    
    df = DataFrame([[v for v in el.values()] for el in data_for_ch], columns=columns)
    ch_client.insert_dataframe(f'INSERT INTO sflow.sflow_1m VALUES', df)
    data_for_ch = []

def main():
    """
    Main function for getting data from Kafka and running enrichment process
    """
    consumer = KafkaConsumer(
        'sflow',
        group_id='sflow_group',
        bootstrap_servers='kafka:9092',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=5000,
        max_poll_interval_ms=5000,
    )
    
    messages = []
    for message in consumer:
        messages.append(message.value)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(enrich, msg) for msg in messages]
        wait(futures)

    ch_insert()

if __name__ == "__main__":
    get_data_from_redis()
    scheduler.start()

    while True:
        main()
        time.sleep(10)
