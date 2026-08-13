"""
GST Calculator Service
======================
Calculates Indian GST for invoice items.

Transaction types:
  'intra'  → CGST + SGST (equal halves of the GST rate)
  'inter'  → IGST (full GST rate)
"""

from decimal import ROUND_HALF_UP, Decimal

TWOPLACES = Decimal("0.01")


def _q(value) -> Decimal:
    """Quantize to 2 decimal places."""
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_item(
    unit_price: float | Decimal,
    quantity: float | Decimal,
    discount: float | Decimal,
    gst_rate: float | Decimal,
    transaction_type: str = "intra",
) -> dict:
    """
    Calculate totals for a single invoice line item.

    Returns a dict with:
      subtotal, taxable_amount, cgst_amount, sgst_amount, igst_amount,
      tax_amount, line_total
    """
    unit_price = _q(unit_price)
    quantity = _q(quantity)
    discount = _q(discount)
    gst_rate = _q(gst_rate)

    subtotal = _q(unit_price * quantity)
    taxable_amount = _q(max(subtotal - discount, Decimal("0")))

    tax_rate_fraction = gst_rate / Decimal("100")

    if transaction_type == "inter":
        igst = _q(taxable_amount * tax_rate_fraction)
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
    else:
        igst = Decimal("0.00")
        half_rate = tax_rate_fraction / Decimal("2")
        cgst = _q(taxable_amount * half_rate)
        sgst = _q(taxable_amount * half_rate)

    tax_amount = _q(cgst + sgst + igst)
    line_total = _q(taxable_amount + tax_amount)

    return {
        "subtotal": subtotal,
        "taxable_amount": taxable_amount,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "tax_amount": tax_amount,
        "line_total": line_total,
    }


def calculate_invoice(items: list[dict], transaction_type: str = "intra") -> dict:
    """
    Aggregate totals across all invoice items.

    Each item dict must have: unit_price, quantity, discount, gst_rate.

    Returns invoice-level totals.
    """
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    taxable_amount = Decimal("0.00")
    cgst_amount = Decimal("0.00")
    sgst_amount = Decimal("0.00")
    igst_amount = Decimal("0.00")

    calculated_items = []
    for item in items:
        calc = calculate_item(
            unit_price=item.get("unit_price", 0),
            quantity=item.get("quantity", 1),
            discount=item.get("discount", 0),
            gst_rate=item.get("gst_rate", 0),
            transaction_type=transaction_type,
        )
        subtotal += calc["subtotal"]
        discount_total += _q(item.get("discount", 0))
        taxable_amount += calc["taxable_amount"]
        cgst_amount += calc["cgst_amount"]
        sgst_amount += calc["sgst_amount"]
        igst_amount += calc["igst_amount"]
        calculated_items.append({**item, **calc})

    total_tax = _q(cgst_amount + sgst_amount + igst_amount)
    total_amount = _q(taxable_amount + total_tax)

    return {
        "items": calculated_items,
        "subtotal": _q(subtotal),
        "discount_total": _q(discount_total),
        "taxable_amount": _q(taxable_amount),
        "cgst_amount": _q(cgst_amount),
        "sgst_amount": _q(sgst_amount),
        "igst_amount": _q(igst_amount),
        "total_tax": total_tax,
        "total_amount": total_amount,
    }


# Supported GST rates in India
GST_RATES = [
    Decimal("0"),
    Decimal("5"),
    Decimal("12"),
    Decimal("18"),
    Decimal("28"),
]
