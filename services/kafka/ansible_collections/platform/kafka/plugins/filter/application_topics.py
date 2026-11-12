"""Parse existing Kafka CLI batch responses without additional CLI invocations."""
import json
import re


def cli_reason(response):
    match = re.search(r'(TopicAuthorizationException|TimeoutException|SSLHandshakeException)', response.get('stderr', ''))
    return match.group(1) if match else 'KAFKA_CLI_FAILED'


def validate_topic(topic, description, properties, phase, provider=''):
    name = topic['name']
    text = '\n'.join(line for line in description.get('stdout', '').splitlines()
                     if re.match(r'^[ \t]*Topic:[ \t]*' + re.escape(name) + r'[ \t]', line))
    result = dict(description=dict(rc=description['rc'], stdout=text, stderr=''), findings=[])
    def fail(code, **extra):
        result['findings'].append(dict(code=code, provider=provider, topic=name, **extra))
        return result
    if int(description['rc']) != 0 or (not text.strip() and (phase == 'verify' or topic['mode'] == 'existing')):
        return fail('APPLICATION_TOPIC_DESCRIBE_FAILED', reason='TOPIC_MISSING' if int(description['rc']) == 0 else cli_reason(description))
    if not text.strip():
        return result
    replicas = re.findall(r'(?:^|[ \t])Replicas:[ \t]*([0-9,]+)', text)
    if (not re.search(r'PartitionCount:[ \t]*' + str(topic['partitions']) + r'(?:[ \t]|$)', text)
            or len(replicas) != topic['partitions']
            or any(len(value.split(',')) != topic['replicationFactor'] for value in replicas)):
        return fail('APPLICATION_TOPIC_DRIFT', expectedPartitions=topic['partitions'], expectedReplicationFactor=topic['replicationFactor'],
                    observedPartitions=re.findall(r'PartitionCount:[ \t]*([0-9]+)', text),
                    observedReplicaCounts=[len(value.split(',')) for value in replicas])
    if re.search(r'Leader:[ \t]*-1(?:[ \t]|$)', text):
        return fail('APPLICATION_TOPIC_REPLICAS_UNAVAILABLE')
    blocks = re.findall(r'(?ms)^All configs for topic ' + re.escape(name) + r' are:[ \t]*\r?\n(.*?)(?=^All configs for topic |\Z)', properties.get('stdout', ''))
    config = '\n'.join(blocks)
    if int(properties['rc']) != 0 or not config.strip():
        return fail('APPLICATION_TOPIC_CONFIG_READ_FAILED', reason=cli_reason(properties))
    for key, value in sorted(topic['config'].items()):
        if not re.search(r'(?m)^[ \t]*' + re.escape(key) + '=' + re.escape(str(value)) + r'[ \t]+sensitive=', config):
            return fail('APPLICATION_TOPIC_CONFIG_DRIFT', property=key)
    return result


def validate_topics(topics, description, properties, phase, provider=''):
    results = {topic['name']: validate_topic(topic, description, properties, phase, provider) for topic in topics}
    return dict(results=results, findings=[finding for value in results.values() for finding in value['findings']])


def application_acl_deltas(accounts, stdout):
    blocks = re.split(r'(?m)^Current ACLs for resource ', stdout)
    observed = set()
    for block in blocks[1:]:
        header = re.match(r'^`([^`\r\n]+)`:[ \t]*\r?\n', block)
        if header is None:
            continue
        for principal, operation in re.findall(
                r'principal=User:([^\r\n]+?), host=\*, operation=([A-Z_]+), permissionType=ALLOW',
                block[header.end():]):
            observed.add((header[1], principal, operation))

    # Account IDs are local to an application and may repeat in a deployment.
    deltas = []
    for account in accounts:
        groups = {}
        for grant in account['grants']:
            kind, name, pattern = (grant[key] for key in ('resourceType', 'name', 'patternType'))
            resource = 'ResourcePattern(resourceType={}, name={}, patternType={})'.format(
                kind.replace('-', '_').upper(), name, pattern.upper())
            missing = [operation for operation in grant['operations']
                       if (resource, account['name'],
                           re.sub(r'([a-z])([A-Z])', r'\1_\2', operation).upper()) not in observed]
            if not missing:
                continue
            # One CLI call grants every operation to every selector.
            group_kind = 'data' if kind in ('topic', 'group', 'transactional-id') else kind
            key = json.dumps([group_kind, pattern, sorted(set(missing))])
            group = groups.setdefault(key, {
                'resources': [], 'selectors': [], 'patternType': pattern,
            })
            group['operations'] = [part for operation in missing for part in ('--operation', operation)]
            resource_key = json.dumps([kind, name])
            if resource_key not in group['resources']:
                group['selectors'].append('--' + kind)
                if kind != 'cluster':
                    group['selectors'].append(name)
            group['resources'].append(resource_key)
        deltas.append(groups)
    return deltas


class FilterModule:
    def filters(self):
        return dict(application_topic_validation=validate_topic, application_topics_validation=validate_topics,
                    application_acl_deltas=application_acl_deltas)
