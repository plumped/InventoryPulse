from admin_dashboard.models import CompanyAddress, CompanyAddressType


def get_address_context(order=None):
    shipping_addresses = CompanyAddress.objects.filter(address_type=CompanyAddressType.SHIPPING)
    billing_addresses = CompanyAddress.objects.filter(address_type=CompanyAddressType.BILLING)

    selected_shipping_address = (order.shipping_address if order else None) or shipping_addresses.filter(is_default=True).first()
    selected_billing_address = (order.billing_address if order else None) or billing_addresses.filter(is_default=True).first()

    return {
        'shipping_addresses': shipping_addresses,
        'billing_addresses': billing_addresses,
        'selected_shipping_address': selected_shipping_address,
        'selected_billing_address': selected_billing_address,
        'all_company_addresses': list(shipping_addresses) + list(billing_addresses),
    }
