import unittest

from lineWebhook import extractMessageFromEvent, parseLineEvents


class ParseLineEventsTests(unittest.TestCase):
    def test_non_object_payload_returns_empty_list(self):
        self.assertEqual(parseLineEvents(b'["not", "an", "object"]'), [])

    def test_event_list_is_returned_for_valid_payload(self):
        payload = b'{"events":[{"type":"message"}]}'
        self.assertEqual(parseLineEvents(payload), [{"type": "message"}])


class ExtractMessageFromEventTests(unittest.TestCase):
    def test_blank_text_is_rejected(self):
        event = {
            "type": "message",
            "message": {"type": "text", "text": "   "},
            "replyToken": "reply",
            "source": {"userId": "user"},
        }
        self.assertIsNone(extractMessageFromEvent(event))

    def test_blank_reply_token_is_rejected(self):
        event = {
            "type": "message",
            "message": {"type": "text", "text": "hello"},
            "replyToken": " ",
            "source": {"userId": "user"},
        }
        self.assertIsNone(extractMessageFromEvent(event))

    def test_blank_user_id_is_rejected(self):
        event = {
            "type": "message",
            "message": {"type": "text", "text": "hello"},
            "replyToken": "reply",
            "source": {"userId": ""},
        }
        self.assertIsNone(extractMessageFromEvent(event))


if __name__ == "__main__":
    unittest.main()
