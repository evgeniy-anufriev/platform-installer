import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/kafka/plugins/filter/application_topics.py'
spec = importlib.util.spec_from_file_location('topic_batch_validation', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TopicBatchValidationTests(unittest.TestCase):
    def setUp(self):
        self.topic = dict(name='events.test', mode='existing', partitions=1, replicationFactor=2,
                          config={'cleanup.policy': 'compact'})
        self.description = dict(rc=0, stdout='Topic: events.test PartitionCount: 1 ReplicationFactor: 2\n'
            '\tTopic: events.test Partition: 0 Leader: 1 Replicas: 1,2 Isr: 1,2')
        self.properties = dict(rc=0, stdout='All configs for topic events.test are:\n  cleanup.policy=compact sensitive=false\n')

    def validate(self, **changes):
        return module.validate_topic(dict(self.topic, **changes), self.description, self.properties, 'apply')['findings']

    def test_valid_and_missing_managed(self):
        self.assertEqual([], self.validate())
        self.description['stdout'] = ''
        self.assertEqual([], self.validate(mode='managed'))
        self.assertEqual('APPLICATION_TOPIC_DESCRIBE_FAILED', self.validate()[0]['code'])

    def test_drift_leader_and_config_are_distinct(self):
        self.assertEqual('APPLICATION_TOPIC_DRIFT', self.validate(replicationFactor=3)[0]['code'])
        self.description['stdout'] = self.description['stdout'].replace('Leader: 1', 'Leader: -1')
        self.assertEqual('APPLICATION_TOPIC_REPLICAS_UNAVAILABLE', self.validate()[0]['code'])
        self.description['stdout'] = self.description['stdout'].replace('Leader: -1', 'Leader: 1')
        self.assertEqual('APPLICATION_TOPIC_CONFIG_DRIFT', self.validate(config={'cleanup.policy': 'delete'})[0]['code'])
        self.properties['stdout'] = ''
        self.assertEqual('APPLICATION_TOPIC_CONFIG_READ_FAILED', self.validate()[0]['code'])

    def test_batch_is_provider_scoped_and_names_are_exact(self):
        result = module.validate_topics([self.topic, dict(self.topic, name='eventsXtest')],
            self.description, self.properties, 'apply', 'qa-kafka')
        self.assertEqual(1, len(result['findings']))
        self.assertEqual('eventsXtest', result['findings'][0]['topic'])
