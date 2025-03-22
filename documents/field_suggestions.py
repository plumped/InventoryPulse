"""
Common field definitions for document templates.

This module provides suggested field definitions for different document types
to make template creation easier.
"""

# Common field definitions for delivery notes
DELIVERY_NOTE_FIELDS = [
    {
        'name': 'Lieferscheinnummer',
        'code': 'delivery_note_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Lieferschein Nr.|Liefersch.-Nr.|Lieferscheinnummer|Delivery Note No.|Delivery Note Number',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Lieferdatum',
        'code': 'delivery_date',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Lieferdatum|Datum|vom|Belegdatum',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Bestellnummer',
        'code': 'order_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Bestellung|Bestellnummer|Ihre Bestellung|Bestell-Nr|Ihre Bestellnummer',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Artikelnummer',
        'code': 'item_number',
        'field_type': 'text',
        'extraction_method': 'table_cell',
        'is_key_field': False,
        'is_required': False
    },
    {
        'name': 'Artikelbezeichnung',
        'code': 'item_description',
        'field_type': 'text',
        'extraction_method': 'table_cell',
        'is_key_field': False,
        'is_required': False
    },
    {
        'name': 'Menge',
        'code': 'quantity',
        'field_type': 'number',
        'extraction_method': 'table_cell',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Einheit',
        'code': 'unit',
        'field_type': 'text',
        'extraction_method': 'table_cell',
        'is_key_field': False,
        'is_required': False
    }
]

# Common field definitions for invoices
INVOICE_FIELDS = [
    {
        'name': 'Rechnungsnummer',
        'code': 'invoice_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Rechnung Nr.|Rech.-Nr.|Rechnungsnummer',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Rechnungsdatum',
        'code': 'invoice_date',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Rechnungsdatum|Datum|vom',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Lieferscheinnummer',
        'code': 'delivery_note_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Lieferschein Nr.|Liefersch.-Nr.|Lieferscheinnummer',
        'is_key_field': True,
        'is_required': False
    },
    {
        'name': 'Bestellnummer',
        'code': 'order_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Bestellung|Bestellnummer|Ihre Bestellung|Bestell-Nr',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Nettobetrag',
        'code': 'net_amount',
        'field_type': 'currency',
        'extraction_method': 'label_based',
        'search_pattern': 'Nettobetrag|Netto',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Mehrwertsteuer',
        'code': 'vat',
        'field_type': 'currency',
        'extraction_method': 'label_based',
        'search_pattern': 'Mehrwertsteuer|MwSt|USt',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Gesamtbetrag',
        'code': 'total_amount',
        'field_type': 'currency',
        'extraction_method': 'label_based',
        'search_pattern': 'Gesamtbetrag|Gesamt|Brutto|Total',
        'is_key_field': False,
        'is_required': True
    }
]

# Common field definitions for quotes
QUOTE_FIELDS = [
    {
        'name': 'Angebotsnummer',
        'code': 'quote_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Angebot Nr.|Ang.-Nr.|Angebotsnummer',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Angebotsdatum',
        'code': 'quote_date',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Angebotsdatum|Datum|vom',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Gültig bis',
        'code': 'valid_until',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Gültig bis|gültig bis|Angebot gültig bis',
        'is_key_field': False,
        'is_required': False
    },
    {
        'name': 'Gesamtbetrag',
        'code': 'total_amount',
        'field_type': 'currency',
        'extraction_method': 'label_based',
        'search_pattern': 'Gesamtbetrag|Gesamt|Brutto|Total',
        'is_key_field': False,
        'is_required': True
    }
]

# Order confirmation fields
ORDER_CONFIRMATION_FIELDS = [
    {
        'name': 'Auftragsbestätigungsnummer',
        'code': 'confirmation_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Auftragsbestätigung Nr.|AB-Nr.|Auftragsbestätigungsnummer',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Bestellnummer',
        'code': 'order_number',
        'field_type': 'text',
        'extraction_method': 'label_based',
        'search_pattern': 'Bestellung|Bestellnummer|Ihre Bestellung|Bestell-Nr',
        'is_key_field': True,
        'is_required': True
    },
    {
        'name': 'Auftragsdatum',
        'code': 'confirmation_date',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Auftragsdatum|Datum|vom',
        'is_key_field': False,
        'is_required': True
    },
    {
        'name': 'Liefertermin',
        'code': 'delivery_date',
        'field_type': 'date',
        'extraction_method': 'label_based',
        'search_pattern': 'Liefertermin|voraussichtlicher Liefertermin|Lieferdatum',
        'is_key_field': False,
        'is_required': False
    }
]

# Map document type codes to field suggestions
FIELD_SUGGESTIONS = {
    'delivery_note': DELIVERY_NOTE_FIELDS,
    'invoice': INVOICE_FIELDS,
    'quote': QUOTE_FIELDS,
    'order_confirmation': ORDER_CONFIRMATION_FIELDS,
}


def get_field_suggestions(document_type_code):
    """
    Get field suggestions for a specific document type.

    Args:
        document_type_code: The code of the document type

    Returns:
        List of suggested fields or empty list if no suggestions found
    """
    return FIELD_SUGGESTIONS.get(document_type_code, [])