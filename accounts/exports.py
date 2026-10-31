"""
accounts/exports.py
CSV export helper that any app can use:

    from accounts.exports import export_csv

    return export_csv(
        "invoices.csv",
        invoices,                                   # queryset or list
        [("Number", "number"),                      # attribute name
         ("Customer", "subscription.customer.name"),  # dotted path
         ("Balance", lambda inv: inv.balance_due)],   # or a function
    )
"""

import csv
from datetime import datetime

from django.http import HttpResponse
from django.utils import timezone

# Cells starting with these can run as formulas when opened in Excel
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _resolve(obj, accessor):
    if callable(accessor):
        return accessor(obj)
    value = obj
    for part in accessor.split("."):
        value = getattr(value, part, None)
        if value is None:
            return ""
        if callable(value):
            value = value()
    return value


def _clean_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def export_csv(filename, rows, columns):
    """Return an HttpResponse that downloads `rows` as a CSV file.

    columns: list of (header, accessor) pairs. An accessor is an attribute
    name, a dotted path like "customer.email", or a function taking the row.
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel opens UTF-8 (₹, names) correctly
    writer = csv.writer(response)
    writer.writerow([header for header, _ in columns])
    for obj in rows:
        writer.writerow([_clean_cell(_resolve(obj, accessor)) for _, accessor in columns])
    return response
