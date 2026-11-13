import json
import unittest

from moblin_remote import protocol


class HashPasswordTest(unittest.TestCase):
    def test_matches_moblins_swift_implementation(self):
        # Known-answer vector computed directly from Moblin's own
        # remoteControlHashPassword(challenge:salt:password:) (CryptoKit SHA256).
        # If this ever stops matching, the real app's hash algorithm changed
        # and the handshake will silently fail against a real phone.
        result = protocol.hash_password(challenge="abc123", salt="def456", password="mypassword")
        self.assertEqual(result, "YosFOKj3YNAO9b/M/yYf+8zcXjVzh/pb1vzgqxo2qiU=")


class MessageCodecTest(unittest.TestCase):
    def test_decode_message_shape(self):
        case, fields = protocol.decode_message('{"identify":{"authentication":"hash"}}')
        self.assertEqual(case, "identify")
        self.assertEqual(fields, {"authentication": "hash"})

    def test_decode_result_extracts_case_name(self):
        self.assertEqual(protocol.decode_result({"result": {"ok": {}}}), "ok")
        self.assertEqual(protocol.decode_result({"result": {"wrongPassword": {}}}), "wrongPassword")

    def test_encode_show_toast_omits_absent_subtitle(self):
        message = json.loads(protocol.encode_show_toast_request(1, "Low quality", None, "warning"))
        data = message["request"]["data"]["showToast"]
        self.assertNotIn("subTitle", data)
        self.assertEqual(data["type"], {"warning": {}})


if __name__ == "__main__":
    unittest.main()
