#!/usr/bin/env python3
import click
from google.cloud import datastore, dns
from google.api_core.exceptions import NotFound
import secrets


@click.group('dynamic-dns-manager')
def manager():
    pass


@manager.command('register')
@click.argument('name')
@click.argument('zone')
@click.option('--project')
def register_client(name, zone, project):
    dns_client = dns.Client(project=project)
    zone_obj = dns_client.zone(zone)
    try:
        zone_obj.reload()
    except NotFound:
        print(f"ERROR: did not find zone {zone}")
        exit(1)

    ds_client = datastore.Client(project=project)

    q = ds_client.query(**dict(kind='dynamic_dns_auth_key'))
    q.add_filter('name', '=', name)
    q.add_filter('zone', '=', zone)
    if list(q.fetch()):
        print(f"ERROR: {name} in {zone} already exists")
        exit(1)

    k = ds_client.key('dynamic_dns_auth_key')
    e = datastore.Entity(k)

    token = secrets.token_hex()

    e['token'] = token
    e['name'] = name
    e['zone'] = zone

    ds_client.put(e)
    print(token, name, zone)


@manager.command('revoke')
@click.argument('name')
@click.argument('zone')
@click.option('--project')
def revoke_client(name, zone, project):
    dns_client = dns.Client(project=project)
    zone_obj = dns_client.zone(zone)
    try:
        zone_obj.reload()
    except NotFound:
        print(f"ERROR: did not find zone {zone}")
        exit(1)

    ds_client = datastore.Client(project=project)

    q = ds_client.query(**dict(kind='dynamic_dns_auth_key'))
    q.add_filter('name', '=', name)
    q.add_filter('zone', '=', zone)
    deletes: list[datastore.Entity] = list(q.fetch())
    if deletes:
        for d in deletes:
            ds_client.delete(d.key)
            print(f"revoked {d.key} entry for {name} in {zone}")


if __name__ == "__main__":
    manager()