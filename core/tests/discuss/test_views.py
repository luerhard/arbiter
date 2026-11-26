from django.urls import reverse
import pytest


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("who", "status"),
    [
        ("anonymous", 302),
        ("annotator", 200),
        ("expert", 403),  # experts decide afterwards, they do not discuss
        ("outsider", 403),
    ],
)
def test_access(get_as, project_discussion, who, status):
    url = reverse("discuss-batch", args=(project_discussion["batch"].id,))

    assert get_as(url, who, project_discussion).status_code == status


@pytest.mark.django_db
def test_page_has_the_metadata_list_for_alpine(get_as, project_discussion):
    # filled in the browser from the room state (cur_metadata), see test_consumers
    url = reverse("discuss-batch", args=(project_discussion["batch"].id,))

    response = get_as(url, "annotator", project_discussion)

    assert b'id="example-metadata"' in response.content
    assert b'x-for="[key, value] in $store.metadata"' in response.content
