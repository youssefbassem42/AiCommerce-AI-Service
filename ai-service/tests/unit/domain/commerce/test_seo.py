from app.domain.commerce.value_objects.seo import SEO


class TestSEO:

    def test_empty_seo(self):
        seo = SEO()
        assert seo.title is None
        assert seo.description is None
        assert seo.url_slug is None

    def test_full_seo(self):
        seo = SEO(
            title="Product Title",
            description="Product description for SEO",
            url_slug="product-title",
        )
        assert seo.title == "Product Title"
        assert seo.url_slug == "product-title"
