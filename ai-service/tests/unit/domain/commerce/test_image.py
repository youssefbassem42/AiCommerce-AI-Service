import pytest

from app.domain.commerce.value_objects.image import Image


class TestImage:

    def test_valid_image(self):
        img = Image(url="https://example.com/img.jpg")
        assert img.url == "https://example.com/img.jpg"
        assert img.alt_text is None

    def test_full_image(self):
        img = Image(
            url="https://example.com/img.jpg",
            alt_text="A product image",
            width=800,
            height=600,
            position=1,
        )
        assert img.alt_text == "A product image"
        assert img.width == 800
        assert img.position == 1

    def test_negative_width_raises(self):
        with pytest.raises(ValueError):
            Image(url="https://example.com/img.jpg", width=-1)

    def test_negative_position_raises(self):
        with pytest.raises(ValueError):
            Image(url="https://example.com/img.jpg", position=-1)

    def test_empty_url_raises(self):
        with pytest.raises(ValueError):
            Image(url="")
