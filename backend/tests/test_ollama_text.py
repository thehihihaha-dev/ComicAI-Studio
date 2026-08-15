import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.ollama_text import call_text_model


class OllamaTextTests(unittest.TestCase):
    @patch("app.services.ollama_text.urllib.request.urlopen")
    def test_parses_markdown_wrapped_json(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"response": "```JSON\n{\"events\": []}\n```"}
        ).encode()
        urlopen.return_value.__enter__.return_value = response

        self.assertEqual(call_text_model("prompt"), {"events": []})

    @patch("app.services.ollama_text.urllib.request.urlopen")
    def test_rejects_empty_response(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({"response": ""}).encode()
        urlopen.return_value.__enter__.return_value = response

        with self.assertRaisesRegex(RuntimeError, "empty response"):
            call_text_model("prompt")


if __name__ == "__main__":
    unittest.main()
