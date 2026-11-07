import pytest
import settings
from scrapy.utils.deprecate import argument_is_required
from scrapy.utils.misc import load_object

# Read from the settings module, not get_project_settings(), which only finds the
# project when pytest runs from scrapers/.
PIPELINE_PATHS = sorted(settings.ITEM_PIPELINES)


def test_every_configured_pipeline_is_checked():
    assert len(PIPELINE_PATHS) == 6


@pytest.mark.parametrize("path", PIPELINE_PATHS)
def test_pipeline_methods_do_not_require_a_spider(path):
    # The check Scrapy runs when it loads a pipeline. It warns when a method
    # requires `spider`, and plans to stop passing it.
    pipeline = load_object(path)

    for name in ("open_spider", "process_item", "close_spider"):
        method = getattr(pipeline, name, None)
        if method is not None:
            assert not argument_is_required(method, "spider"), f"{path}.{name}"
