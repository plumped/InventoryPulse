from django import template

register = template.Library()

@register.filter
def get_address_by_type(supplier, address_type):
    """Template-Filter zum Abrufen einer Adresse nach Typ."""
    return supplier.get_default_address(address_type)

@register.filter
def get_contact_by_type(supplier, contact_type):
    """Template-Filter zum Abrufen eines Kontakts nach Typ."""
    return supplier.get_default_contact(contact_type)

@register.filter
def filter_addresses_by_type(addresses, address_type):
    """Filter addresses by address type."""
    return addresses.filter(address_type=address_type)

@register.filter
def filter_contacts_by_type(contacts, contact_type):
    """Filter contacts by contact type."""
    return contacts.filter(contact_type=contact_type)