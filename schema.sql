CREATE DATABASE IF NOT EXISTS sflow;

CREATE TABLE IF NOT EXISTS sflow.sflow_1m
(
    timestamp DateTime,
    dc String,
    agent_ip IPv4,
    agent_name String,
    in_iface UInt8,
    src_site String,
    dst_site String,
    src_ip IPv4,
    dst_ip IPv4,
    src_hostname String,
    dst_hostname String,
    proto String,
    src_port UInt16,
    dst_port UInt16,
    packets UInt32,
    bytes UInt64
)
ENGINE = MergeTree
ORDER BY (dc, timestamp)
TTL timestamp + INTERVAL 1 MONTH;
