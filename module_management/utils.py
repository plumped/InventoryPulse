from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def is_feature_available(company, feature_code):
    """
    Prüft, ob ein bestimmtes Feature für ein Unternehmen verfügbar ist.
    """
    # Wenn kein Unternehmen zugewiesen, prüfe Settings für Entwicklungsmodus
    if not company:
        return getattr(settings, 'DEVELOPMENT_MODE', False)

    # Prüfe Feature-Flags des Pakets
    if company.subscription_package:
        feature_flags = company.get_feature_flags()
        if feature_code in feature_flags:
            return feature_flags[feature_code]

    # Fallback: Prüfe, ob das Feature in einer Liste erlaubter Features ist
    if hasattr(company, 'allowed_features'):
        return feature_code in company.allowed_features

    return False


def get_subscription_level(company):
    """
    Gibt das Subscription-Level eines Unternehmens zurück.
    """
    if not company or not company.subscription_package:
        return 'basic'  # Standard-Level

    return company.subscription_package.package_type


def calculate_expiry_date(renewal_type):
    """Berechnet das Ablaufdatum basierend auf dem Verlängerungstyp"""
    today = timezone.now().date()

    if renewal_type == 'monthly':
        return today + timedelta(days=30)
    elif renewal_type == 'yearly':
        return today + timedelta(days=365)

    # Standardwert: 30 Tage
    return today + timedelta(days=30)
