import unittest

from lineWebhook import parseLineEvents


class ParseLineEventsTests(unittest.TestCase):
    def test_non_object_payload_returns_empty_list(self):
        self.assertEqual(parseLineEvents(b'["not", "an", "object"]'), [])

    def test_event_list_is_returned_for_valid_payload(self):
        payload = b'{"events":[{"type":"message"}]}'
        self.assertEqual(parseLineEvents(payload), [{"type": "message"}])


if __name__ == "__main__":
    unittest.main()
