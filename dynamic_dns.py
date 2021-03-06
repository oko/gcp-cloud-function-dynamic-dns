import ipaddress
from flask import jsonify

from google.cloud import dns, datastore
from typing import Sequence

import time
import os


PROJECT = os.environ.get('GCP_PROJECT', 'example-project')


def auth_token_lookup(client, token):
    """
    Validate a provided client token against cloud datastore

    Expected datastore format for use is:
    * Autogenerated ID
    * Properties:
        * "token": the token to use
        * "name": the name of the host (*sans zone name*)
        * "zone": the GCP zone name (*not the DNS name*)

    For example:

    id/abcdefghijklmnop
    token=sha256sumofrandomness
    name=laptop.computers
    zone=example-com

    Where the DNS name of example-com is example.com.

    This would map to a client whose ultimate FQDN would be:

    laptop.computers.example.com

    :param client: Google Cloud Datastore client
    :param token: token to validate
    :return:
    """
    query = client.query(**dict(kind='dynamic_dns_auth_key'))
    query.add_filter('token', '=', token)
    result = list(query.fetch())
    if len(result) < 1:
        return None
    else:
        return result[0]


def dynamic_dns(req):
    if not req.headers.get('x-forwarded-for'):
        addr = req.remote_addr
    else:
        addr = req.headers['x-forwarded-for'].split(',')[0].strip()

    auth_token = req.headers['x-token']

    ip = ipaddress.ip_address(addr)
    if type(ip) is ipaddress.IPv6Address:
        record_type = "AAAA"
    else:
        record_type = "A"

    client = dns.Client(project=PROJECT)

    ds_client = datastore.Client(project=PROJECT)

    # check authentication against cloud datastore
    auth_check = auth_token_lookup(ds_client, auth_token)
    if not auth_check:
        return jsonify({'error': 'invalid auth token'}), 401

    # load zone and record sets
    zone: dns.ManagedZone = client.zone(auth_check['zone'])
    zone.reload()

    fqdn = f"{auth_check['name']}.{zone.dns_name}"
    rrsets: Sequence[dns.ResourceRecordSet] = zone.list_resource_record_sets()

    # find any existing record sets *of this request's type* for drop
    existing = []
    for rrset in rrsets:
        if rrset.name == fqdn and rrset.record_type == record_type:
            existing.append(rrset)
            if ipaddress.ip_address(rrset.rrdatas[0]) == ip:
                return jsonify({'message': 'already up to date'}), 200

    changes = zone.changes()

    # mark existing record sets for drop
    if existing:
        for e in existing:
            changes.delete_record_set(e)

    # create new record set for add
    record_set = zone.resource_record_set(fqdn, record_type, 300, [ip.exploded])
    changes.add_record_set(record_set)

    # add changes and wait for completion
    changes.create()
    while changes.status != 'done':
        print('waiting for changes')
        time.sleep(0.5)
        changes.reload()

    output = {
        'record_type': record_type,
        'ip': ip.exploded,
    }
    return jsonify(output)