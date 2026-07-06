import unittest
import base64
import hashlib
import hmac
import os

from lineWebhook import extractMessageFromEvent, parseLineEvents, validateLineSignature


class ValidateLineSignatureTests(unittest.TestCase):
    def test_header_lookup_is_case_insensitive(self):
        secret = "test-secret"
        body = b'{"events":[]}'
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode("utf-8")

        original_secret = os.environ.get("LINE_CHANNEL_SECRET")
        os.environ["LINE_CHANNEL_SECRET"] = secret
        try:
            self.assertTrue(validateLineSignature({"X-Line-Signature": signature}, body))
        finally:
            if original_secret is None:
                os.environ.pop("LINE_CHANNEL_SECRET", None)
            else:
                os.environ["LINE_CHANNEL_SECRET"] = original_secret


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
