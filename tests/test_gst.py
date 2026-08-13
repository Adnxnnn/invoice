"""GST Calculator Tests"""
from decimal import Decimal
import pytest
from invoicepro.services.gst_calculator import calculate_item, calculate_invoice, GST_RATES


def test_calculate_item_intra():
    """Intra-state: tax splits into CGST + SGST."""
    result = calculate_item(unit_price=1000, quantity=1, discount=0, gst_rate=18, transaction_type="intra")
    assert result["subtotal"] == Decimal("1000.00")
    assert result["taxable_amount"] == Decimal("1000.00")
    assert result["cgst_amount"] == Decimal("90.00")
    assert result["sgst_amount"] == Decimal("90.00")
    assert result["igst_amount"] == Decimal("0.00")
    assert result["tax_amount"] == Decimal("180.00")
    assert result["line_total"] == Decimal("1180.00")


def test_calculate_item_inter():
    """Inter-state: tax goes to IGST only."""
    result = calculate_item(unit_price=1000, quantity=1, discount=0, gst_rate=18, transaction_type="inter")
    assert result["cgst_amount"] == Decimal("0.00")
    assert result["sgst_amount"] == Decimal("0.00")
    assert result["igst_amount"] == Decimal("180.00")
    assert result["line_total"] == Decimal("1180.00")


def test_calculate_item_with_discount():
    """Discount reduces the taxable amount."""
    result = calculate_item(unit_price=1000, quantity=2, discount=200, gst_rate=18, transaction_type="intra")
    # subtotal = 2000, discount = 200, taxable = 1800
    assert result["subtotal"] == Decimal("2000.00")
    assert result["taxable_amount"] == Decimal("1800.00")
    assert result["cgst_amount"] == Decimal("162.00")
    assert result["sgst_amount"] == Decimal("162.00")
    assert result["line_total"] == Decimal("2124.00")


def test_calculate_item_zero_gst():
    """Zero-rated item: no tax."""
    result = calculate_item(unit_price=500, quantity=3, discount=0, gst_rate=0, transaction_type="intra")
    assert result["tax_amount"] == Decimal("0.00")
    assert result["line_total"] == result["subtotal"]


def test_calculate_invoice_aggregation():
    """Invoice totals aggregate correctly across multiple items."""
    items = [
        {"unit_price": 1000, "quantity": 1, "discount": 0,   "gst_rate": 18},
        {"unit_price": 500,  "quantity": 2, "discount": 100, "gst_rate": 12},
    ]
    result = calculate_invoice(items, transaction_type="intra")
    # Item 1: taxable=1000, tax=180, total=1180
    # Item 2: subtotal=1000, disc=100, taxable=900, tax=108, total=1008
    assert result["subtotal"] == Decimal("2000.00")
    assert result["discount_total"] == Decimal("100.00")
    assert result["taxable_amount"] == Decimal("1900.00")
    assert result["cgst_amount"] == Decimal("90.00") + Decimal("54.00")
    assert result["sgst_amount"] == Decimal("90.00") + Decimal("54.00")
    assert result["total_amount"] == Decimal("2188.00")


def test_gst_rates_list():
    """Standard GST rate list is present."""
    assert Decimal("0")  in GST_RATES
    assert Decimal("5")  in GST_RATES
    assert Decimal("18") in GST_RATES
    assert Decimal("28") in GST_RATES


def test_discount_cannot_go_negative():
    """Discount exceeding subtotal doesn't produce negative taxable."""
    result = calculate_item(unit_price=100, quantity=1, discount=9999, gst_rate=18, transaction_type="intra")
    assert result["taxable_amount"] == Decimal("0.00")
    assert result["line_total"] == Decimal("0.00")
