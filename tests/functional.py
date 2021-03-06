import time
import unittest
import os.path
from six.moves.urllib.parse import urljoin

import requests

from kinto_signer.serializer import canonical_json
from kinto_signer.signer import local_ecdsa

from kinto_http import Client, KintoException

__HERE__ = os.path.abspath(os.path.dirname(__file__))

SERVER_URL = "http://localhost:8888/v1"
DEFAULT_AUTH = ('user', 'p4ssw0rd')


def collection_timestamp(client):
    # XXXX Waiting https://github.com/Kinto/kinto-http.py/issues/77
    endpoint = client.get_endpoint('records')
    record_resp, headers = client.session.request('get', endpoint)
    return headers.get('ETag', '').strip('"')


def user_principal(client):
    return client.server_info()['user']['id']


def create_records(client):
    # Create some data on the client collection and send it.
    with client.batch() as batch:
        for n in range(0, 10):
            batch.create_record(data={'newdata': n})


def flush_server(server_url):
    flush_url = urljoin(server_url, '/__flush__')
    resp = requests.post(flush_url)
    resp.raise_for_status()


class BaseTestFunctional(object):
    server_url = SERVER_URL

    @classmethod
    def setUpClass(cls):
        super(BaseTestFunctional, cls).setUpClass()
        cls.signer = local_ecdsa.ECDSASigner(private_key=cls.private_key)
        cls.source = Client(
            server_url=cls.server_url,
            auth=DEFAULT_AUTH,
            bucket=cls.source_bucket,
            collection=cls.source_collection)
        cls.destination = Client(
            server_url=cls.server_url,
            auth=DEFAULT_AUTH,
            bucket=cls.destination_bucket,
            collection=cls.destination_collection)
        cls.editor_client = Client(
            server_url=cls.server_url,
            auth=("editor", ""),
            bucket=cls.source_bucket,
            collection=cls.source_collection)
        cls.someone_client = Client(
            server_url=cls.server_url,
            auth=("Sam", "Wan-Elss"),
            bucket=cls.source_bucket,
            collection=cls.source_collection)

    def tearDown(self):
        # Delete all the created objects.
        flush_server(self.server_url)

    def setUp(self):
        # Give the permission to write in collection to anybody
        self.source.create_bucket()
        perms = {"write": ["system.Authenticated"]}
        self.source.create_collection(permissions=perms)
        principals = [user_principal(self.editor_client),
                      user_principal(self.someone_client),
                      user_principal(self.source)]
        create_group(self.source, "editors", members=principals)
        create_group(self.source, "reviewers", members=principals)

        # Create some data on the source collection and send it.
        create_records(self.source)

        self.source_records = self.source.get_records()
        assert len(self.source_records) == 10

        time.sleep(0.1)

        self.trigger_signature()

    def trigger_signature(self, reviewer_client=None):
        self.editor_client.patch_collection(data={'status': 'to-review'})
        if reviewer_client is None:
            reviewer_client = self.source
        reviewer_client.patch_collection(data={'status': 'to-sign'})

    def test_groups_and_reviewers_are_forced(self):
        capability = self.source.server_info()['capabilities']['signer']
        assert capability['group_check_enabled']
        assert capability['to_review_enabled']

    def test_heartbeat_is_successful(self):
        hb_url = urljoin(self.server_url, '/__heartbeat__')
        resp = requests.get(hb_url)
        resp.raise_for_status()

    def test_metadata_attributes(self):
        # Ensure the destination data is signed properly.
        destination_collection = self.destination.get_collection()['data']
        signature = destination_collection['signature']
        assert signature is not None

        # the status of the source collection should be "signed".
        source_collection = self.source.get_collection()['data']
        assert source_collection['status'] == 'signed'

        assert (collection_timestamp(self.source) ==
                collection_timestamp(self.source))

    def test_destination_creation_and_new_records_signature(self):
        # Create some records and trigger another signature.
        self.source.create_record({'newdata': 'hello'})
        self.source.create_record({'newdata': 'bonjour'})

        time.sleep(0.1)

        self.trigger_signature()
        data = self.destination.get_collection()
        signature = data['data']['signature']
        assert signature is not None

        records = self.destination.get_records()
        assert len(records) == 12
        last_modified = collection_timestamp(self.destination)
        serialized_records = canonical_json(records, last_modified)
        # This raises when the signature is invalid.
        self.signer.verify(serialized_records, signature)

    def test_records_update_and_signature(self):
        # Update some records and trigger another signature.
        updated = self.source_records[5].copy()
        updated['newdata'] = 'bump'
        self.source.update_record(updated)
        updated = self.source_records[0].copy()
        updated['newdata'] = 'hoop'
        self.source.update_record(updated)

        time.sleep(0.1)

        self.trigger_signature()
        data = self.destination.get_collection()
        signature = data['data']['signature']
        assert signature is not None

        records = self.destination.get_records()
        assert len(records) == 10
        last_modified = collection_timestamp(self.destination)
        serialized_records = canonical_json(records, last_modified)
        # This raises when the signature is invalid.
        self.signer.verify(serialized_records, signature)

    def test_records_deletion_and_signature(self):
        # Now delete one record on the source and trigger another signature.
        self.source.delete_record(self.source_records[1]['id'])
        self.source.delete_record(self.source_records[5]['id'])

        time.sleep(0.1)

        self.trigger_signature()

        data = self.destination.get_collection()
        signature = data['data']['signature']
        assert signature is not None

        records = self.destination.get_records(_since=0)  # obtain deleted too
        last_modified = collection_timestamp(self.destination)
        serialized_records = canonical_json(records, last_modified)

        assert len(records) == 10  # two of them are deleted.
        assert len([r for r in records if r.get('deleted', False)]) == 2

        # This raises when the signature is invalid.
        self.signer.verify(serialized_records, signature)

    def test_records_delete_all_and_signature(self):
        source_records = self.source.get_records()
        destination_records = self.destination.get_records()

        assert len(source_records) == len(destination_records)

        self.source.delete_records()

        self.trigger_signature()

        source_records = self.source.get_records()
        destination_records = self.destination.get_records()

        assert len(source_records) == len(destination_records) == 0

        last_modified = collection_timestamp(self.destination)
        serialized_records = canonical_json(destination_records, last_modified)
        # print("VERIFIED", serialized_records)

        data = self.destination.get_collection()
        signature = data['data']['signature']
        assert signature is not None

        # This raises when the signature is invalid.
        self.signer.verify(serialized_records, signature)

    def test_distinct_users_can_trigger_signatures(self):
        collection = self.destination.get_collection()
        before = collection['data']['signature']

        self.source.create_record(data={"pim": "pam"})
        # Trigger a signature as someone else.
        self.trigger_signature(reviewer_client=self.someone_client)

        collection = self.destination.get_collection()
        after = collection['data']['signature']

        assert before != after


class AliceFunctionalTest(BaseTestFunctional, unittest.TestCase):
    private_key = os.path.join(__HERE__, 'config/ecdsa.private.pem')
    source_bucket = "alice"
    destination_bucket = "alice"
    source_collection = "source"
    destination_collection = "destination"


# Signer is configured to use a different key for Bob and Alice.
class BobFunctionalTest(BaseTestFunctional, unittest.TestCase):
    private_key = os.path.join(__HERE__, 'config/bob.ecdsa.private.pem')
    source_bucket = "bob"
    source_collection = "source"
    destination_bucket = "bob"
    destination_collection = "destination"


def create_group(client, name, members):
    endpoint = client.get_endpoint('collections')
    endpoint = endpoint.replace('/collections', '/groups/%s' % name)
    data = {"members": members}
    resp, headers = client.session.request('put', endpoint, data)
    return resp


class WorkflowTest(unittest.TestCase):
    server_url = SERVER_URL

    @classmethod
    def setUpClass(cls):
        super(WorkflowTest, cls).setUpClass()
        client_kw = dict(server_url=cls.server_url,
                         bucket="alice",
                         collection="from")
        cls.client = Client(auth=DEFAULT_AUTH, **client_kw)
        cls.elsa_client = Client(auth=('elsa', ''), **client_kw)
        cls.anna_client = Client(auth=('anna', ''), **client_kw)
        cls.client_principal = user_principal(cls.client)
        cls.elsa_principal = user_principal(cls.elsa_client)
        cls.anna_principal = user_principal(cls.anna_client)

    def setUp(self):
        perms = {"write": ["system.Authenticated"]}
        self.client.create_bucket()
        create_group(self.client, "editors", members=[self.anna_principal,
                                                      self.client_principal])
        create_group(self.client, "reviewers", members=[self.elsa_principal,
                                                        self.client_principal])
        self.client.create_collection(permissions=perms)

    def tearDown(self):
        # Delete all the created objects.
        flush_server(self.server_url)

    def test_status_work_in_progress(self):
        collection = self.client.get_collection()
        assert 'status' not in collection['data']

        create_records(self.client)

        collection = self.client.get_collection()
        after = collection['data']['status']
        assert after == 'work-in-progress'

    def test_whole_workflow(self):
        create_records(self.client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'to-sign'})
        status = self.client.get_collection()['data']['status']
        assert status == 'signed'

    def test_only_editors_can_ask_for_review(self):
        with self.assertRaises(KintoException):
            self.elsa_client.patch_collection(data={'status': 'to-review'})

    def test_status_can_be_maintained_as_to_review(self):
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'to-review'})

    def test_same_editor_cannot_review(self):
        self.anna_client.patch_collection(data={'status': 'to-review'})
        with self.assertRaises(KintoException):
            self.anna_client.patch_collection(data={'status': 'to-sign'})

    def test_status_cannot_be_set_to_sign_without_review(self):
        with self.assertRaises(KintoException):
            self.elsa_client.patch_collection(data={'status': 'to-sign'})

    def test_review_can_be_cancelled_by_editor(self):
        create_records(self.client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.anna_client.patch_collection(data={'status': 'work-in-progress'})
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'to-sign'})

    def test_review_can_be_cancelled_by_reviewer(self):
        create_records(self.client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'work-in-progress'})
        create_records(self.anna_client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'to-sign'})

    def test_must_ask_for_review_after_cancelled(self):
        create_records(self.client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        self.elsa_client.patch_collection(data={'status': 'work-in-progress'})
        with self.assertRaises(KintoException):
            self.elsa_client.patch_collection(data={'status': 'to-sign'})

    def test_editors_can_be_different_after_cancelled(self):
        create_records(self.client)
        self.client.patch_collection(data={'status': 'to-review'})
        # Client cannot review since he is the last_editor.
        with self.assertRaises(KintoException):
            self.client.patch_collection(data={'status': 'to-sign'})
        # Someone rejects the review.
        self.elsa_client.patch_collection(data={'status': 'work-in-progress'})
        # Anna becomes the last_editor.
        self.anna_client.patch_collection(data={'status': 'to-review'})
        # Client can now review because he is not the last_editor.
        self.client.patch_collection(data={'status': 'to-sign'})

    def test_modifying_the_collection_resets_status(self):
        create_records(self.client)
        self.anna_client.patch_collection(data={'status': 'to-review'})
        create_records(self.client)
        status = self.client.get_collection()['data']['status']
        assert status == 'work-in-progress'
