import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.ollama_vision import call_vision_model


class OllamaResponseParsingTests(unittest.TestCase):
    @patch("app.services.ollama_vision.urllib.request.urlopen")
    @patch("builtins.open")
    def test_parses_case_insensitive_markdown_fence(self, image_open, urlopen):
        image_open.return_value.__enter__.return_value.read.return_value = b"image"
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"response": "```JSON\n{\"regions\": []}\n```"}
        ).encode()
        urlopen.return_value.__enter__.return_value = response

        result = call_vision_model("page.jpg", "prompt")

        self.assertEqual(result, {"regions": []})


if __name__ == "__main__":
    unittest.main()
