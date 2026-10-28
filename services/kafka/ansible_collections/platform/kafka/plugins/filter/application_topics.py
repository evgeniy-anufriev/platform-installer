"""Parse existing Kafka CLI batch responses without additional CLI invocations."""
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


class FilterModule:
    def filters(self):
        return dict(application_topic_validation=validate_topic, application_topics_validation=validate_topics)
