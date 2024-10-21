from django import template

register = template.Library()


@register.filter
def zip_lists(a, b):
    """zip two iterables together"""
    return zip(a, b, strict=True)
