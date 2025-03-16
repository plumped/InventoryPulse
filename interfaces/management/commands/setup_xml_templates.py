# interfaces/management/commands/setup_xml_templates.py

from django.core.management.base import BaseCommand
from django.db import transaction
from interfaces.models import XMLStandardTemplate


class Command(BaseCommand):
    help = 'Initialisiert die XML-Standardvorlagen für Lieferantenschnittstellen'

    def handle(self, *args, **options):
        self.stdout.write("Initialisiere XML-Standardvorlagen...")

        # Liste aller Template-Definitionen
        templates = [
            # UBL 2.1 (Universal Business Language)
            {
                'name': 'UBL 2.1 Bestellung',
                'code': 'ubl_2_1_order',
                'description': 'Universal Business Language (UBL) 2.1 Standard für Bestellungen, OASIS-Standard.',
                'industry': 'Allgemein',
                'version': '2.1',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<Order xmlns="urn:oasis:names:specification:ubl:schema:xsd:Order-2"
       xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
       xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:ID>{{ order.order_number }}</cbc:ID>
  <cbc:IssueDate>{{ order.order_date|date:"Y-m-d" }}</cbc:IssueDate>
  <cbc:OrderTypeCode>220</cbc:OrderTypeCode>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>

  <cac:BuyerCustomerParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>{{ order.company_name|default:"Ihre Firma GmbH" }}</cbc:Name>
      </cac:PartyName>
    </cac:Party>
  </cac:BuyerCustomerParty>

  <cac:SellerSupplierParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>{{ supplier.name }}</cbc:Name>
      </cac:PartyName>
      <cac:PartyIdentification>
        <cbc:ID>{{ supplier.id }}</cbc:ID>
      </cac:PartyIdentification>
    </cac:Party>
  </cac:SellerSupplierParty>

  {% for item in items %}
  <cac:OrderLine>
    <cbc:LineID>{{ forloop.counter }}</cbc:LineID>
    <cac:LineItem>
      <cbc:ID>{{ item.id }}</cbc:ID>
      <cbc:Quantity unitCode="EA">{{ item.quantity_ordered }}</cbc:Quantity>
      <cbc:LineExtensionAmount currencyID="EUR">{{ item.line_total }}</cbc:LineExtensionAmount>
      <cac:Price>
        <cbc:PriceAmount currencyID="EUR">{{ item.unit_price }}</cbc:PriceAmount>
      </cac:Price>
      <cac:Item>
        <cbc:Name>{{ item.product.name }}</cbc:Name>
        <cac:SellersItemIdentification>
          <cbc:ID>{{ item.supplier_sku }}</cbc:ID>
        </cac:SellersItemIdentification>
        <cac:BuyersItemIdentification>
          <cbc:ID>{{ item.product.sku }}</cbc:ID>
        </cac:BuyersItemIdentification>
      </cac:Item>
    </cac:LineItem>
  </cac:OrderLine>
  {% endfor %}
</Order>
"""
            },

            # VDA 4905 (Verband der Automobilindustrie)
            {
                'name': 'VDA 4905 Lieferabruf',
                'code': 'vda_4905',
                'description': 'VDA 4905 Standard für Lieferabrufe in der Automobilindustrie.',
                'industry': 'Automobilindustrie',
                'version': '4905',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<LIEFERABRUF>
  <KOPF>
    <BESTELLNUMMER>{{ order.order_number }}</BESTELLNUMMER>
    <BESTELLDATUM>{{ order.order_date|date:"Ymd" }}</BESTELLDATUM>
    <ABRUFNUMMER>{{ order.id }}</ABRUFNUMMER>
    <ABRUFDATUM>{{ order.order_date|date:"Ymd" }}</ABRUFDATUM>
    <BESTELLER>{{ order.company_name|default:"Ihre Firma GmbH" }}</BESTELLER>
    <LIEFERANT>
      <LIEFERANTENNUMMER>{{ supplier.id }}</LIEFERANTENNUMMER>
      <LIEFERANTENNAME>{{ supplier.name }}</LIEFERANTENNAME>
    </LIEFERANT>
  </KOPF>
  <POSITIONEN>
    {% for item in items %}
    <POSITION>
      <POSITIONSNUMMER>{{ forloop.counter }}</POSITIONSNUMMER>
      <TEILENUMMER>{{ item.supplier_sku }}</TEILENUMMER>
      <TEILEBEZEICHNUNG>{{ item.product.name }}</TEILEBEZEICHNUNG>
      <MENGE>{{ item.quantity_ordered }}</MENGE>
      <MENGENEINHEIT>ST</MENGENEINHEIT>
      <EINZELPREIS>{{ item.unit_price }}</EINZELPREIS>
      <WAEHRUNG>EUR</WAEHRUNG>
    </POSITION>
    {% endfor %}
  </POSITIONEN>
  <ZUSAMMENFASSUNG>
    <GESAMTMENGE>{{ order.items.all|length }}</GESAMTMENGE>
    <GESAMTPREIS>{{ order.total }}</GESAMTPREIS>
    <WAEHRUNG>EUR</WAEHRUNG>
  </ZUSAMMENFASSUNG>
</LIEFERABRUF>
"""
            },

            # BMEcat 2005 (Elektronischer Datenaustausch)
            {
                'name': 'BMEcat 2005 Bestellung',
                'code': 'bmecat_2005_order',
                'description': 'BMEcat 2005 Standard für elektronische Bestellungen.',
                'industry': 'Allgemein',
                'version': '2005',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ORDER SYSTEM "bmecat_2005.dtd">
<ORDER version="2005">
  <ORDER_HEADER>
    <ORDER_INFO>
      <ORDER_ID>{{ order.order_number }}</ORDER_ID>
      <ORDER_DATE>{{ order.order_date|date:"Y-m-d" }}</ORDER_DATE>
      <DELIVERY_DATE>{{ order.delivery_date|date:"Y-m-d"|default:"" }}</DELIVERY_DATE>
      <SUPPLIER>
        <SUPPLIER_ID>{{ supplier.id }}</SUPPLIER_ID>
        <SUPPLIER_NAME>{{ supplier.name }}</SUPPLIER_NAME>
      </SUPPLIER>
      <BUYER>
        <BUYER_ID>{{ order.company_id|default:"" }}</BUYER_ID>
        <BUYER_NAME>{{ order.company_name|default:"Ihre Firma GmbH" }}</BUYER_NAME>
      </BUYER>
    </ORDER_INFO>
  </ORDER_HEADER>
  <ORDER_ITEM_LIST>
    {% for item in items %}
    <ORDER_ITEM>
      <LINE_ITEM_ID>{{ forloop.counter }}</LINE_ITEM_ID>
      <ARTICLE_ID>
        <SUPPLIER_AID>{{ item.supplier_sku }}</SUPPLIER_AID>
        <BUYER_AID>{{ item.product.sku }}</BUYER_AID>
      </ARTICLE_ID>
      <ARTICLE_DESCRIPTION>
        <DESCRIPTION_SHORT>{{ item.product.name }}</DESCRIPTION_SHORT>
      </ARTICLE_DESCRIPTION>
      <QUANTITY>{{ item.quantity_ordered }}</QUANTITY>
      <ORDER_UNIT>C62</ORDER_UNIT>
      <PRICE_LINE_AMOUNT>{{ item.line_total }}</PRICE_LINE_AMOUNT>
      <PRICE_AMOUNT>{{ item.unit_price }}</PRICE_AMOUNT>
    </ORDER_ITEM>
    {% endfor %}
  </ORDER_ITEM_LIST>
  <ORDER_SUMMARY>
    <TOTAL_AMOUNT>{{ order.total }}</TOTAL_AMOUNT>
    <TOTAL_TAX>{{ order.tax }}</TOTAL_TAX>
  </ORDER_SUMMARY>
</ORDER>
"""
            },

            # EDIFACT ORDERS (Electronic Data Interchange For Administration Commerce and Transport)
            {
                'name': 'EDIFACT ORDERS D96A',
                'code': 'edifact_orders_d96a',
                'description': 'EDIFACT ORDERS D96A Standard für elektronische Bestellungen.',
                'industry': 'Logistik, Transport, Handel',
                'version': 'D96A',
                'template': """UNA:+.? '
UNB+UNOC:3+{{ order.company_id|default:"SENDERID" }}:14+{{ supplier.id|default:"RECEIVERID" }}:14+{{ order.order_date|date:"Ymd" }}:{{ order.order_date|date:"Hi" }}+{{ order.id }}+++++1'
UNH+1+ORDERS:D:96A:UN:EAN008'
BGM+220+{{ order.order_number }}+9'
DTM+137:{{ order.order_date|date:"YmdHi" }}:203'
NAD+BY+{{ order.company_id|default:"BUYERID" }}::9++{{ order.company_name|default:"BUYER NAME" }}'
NAD+SU+{{ supplier.id }}::9++{{ supplier.name }}'
{% for item in items %}
LIN+{{ forloop.counter }}++{{ item.supplier_sku }}:EN'
PIA+5+{{ item.product.sku }}:IN'
IMD+F++:::{{ item.product.name }}'
QTY+21:{{ item.quantity_ordered }}'
PRI+AAA:{{ item.unit_price }}'
MOA+203:{{ item.line_total }}'
{% endfor %}
UNS+S'
MOA+79:{{ order.subtotal }}'
MOA+176:{{ order.total }}'
MOA+124:{{ order.tax }}'
UNT+{{ items|length|add:"14" }}+1'
UNZ+1+{{ order.id }}'
"""
            },

            # RosettaNet PIP 3A4 (Purchase Order Request)
            {
                'name': 'RosettaNet PIP 3A4',
                'code': 'rosettanet_pip_3a4',
                'description': 'RosettaNet PIP 3A4 Standard für Bestellungsanfragen in der Elektronik- und Hightech-Industrie.',
                'industry': 'Elektronik, Hightech',
                'version': '3A4',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<Pip3A4PurchaseOrderRequest xmlns="urn:rosettanet:specification:interchange:PurchaseOrderRequest:xsd:schema:02.05">
  <fromRole>
    <PartnerRoleDescription>Buyer</PartnerRoleDescription>
    <ContactInformation>
      <ContactName>{{ order.contact_name|default:"" }}</ContactName>
      <EmailAddress>{{ order.contact_email|default:"" }}</EmailAddress>
    </ContactInformation>
    <GlobalPartnerRoleClassificationCode>Buyer</GlobalPartnerRoleClassificationCode>
    <PartnerDescription>
      <BusinessDescription>{{ order.company_name|default:"Ihre Firma GmbH" }}</BusinessDescription>
    </PartnerDescription>
  </fromRole>
  <toRole>
    <PartnerRoleDescription>Seller</PartnerRoleDescription>
    <GlobalPartnerRoleClassificationCode>Seller</GlobalPartnerRoleClassificationCode>
    <PartnerDescription>
      <BusinessDescription>{{ supplier.name }}</BusinessDescription>
      <GlobalBusinessIdentifier>{{ supplier.id }}</GlobalBusinessIdentifier>
    </PartnerDescription>
  </toRole>
  <thisDocumentGenerationDateTime>{{ order.order_date|date:"Y-m-d" }}T{{ order.order_date|date:"H:i:s" }}Z</thisDocumentGenerationDateTime>
  <PurchaseOrder>
    <ProductLineItem>
      {% for item in items %}
      <LineNumber>{{ forloop.counter }}</LineNumber>
      <OrderQuantity>
        <ProductQuantity>{{ item.quantity_ordered }}</ProductQuantity>
        <UnitOfMeasure>Each</UnitOfMeasure>
      </OrderQuantity>
      <ProductIdentification>
        <PartnerProductIdentification>
          <GlobalProductIdentifier>{{ item.supplier_sku }}</GlobalProductIdentifier>
          <PartnerProductIdentification>{{ item.product.sku }}</PartnerProductIdentification>
        </PartnerProductIdentification>
      </ProductIdentification>
      <LineItemProductDescription>{{ item.product.name }}</LineItemProductDescription>
      <RequestedPrice>
        <FinancialAmount>
          <GlobalCurrencyCode>EUR</GlobalCurrencyCode>
          <MonetaryAmount>{{ item.unit_price }}</MonetaryAmount>
        </FinancialAmount>
      </RequestedPrice>
      <TotalLineItemAmount>
        <FinancialAmount>
          <GlobalCurrencyCode>EUR</GlobalCurrencyCode>
          <MonetaryAmount>{{ item.line_total }}</MonetaryAmount>
        </FinancialAmount>
      </TotalLineItemAmount>
      {% endfor %}
    </ProductLineItem>
    <PurchaseOrderType>New</PurchaseOrderType>
    <GlobalDocumentFunctionCode>Request</GlobalDocumentFunctionCode>
    <GlobalPurchaseOrderTypeCode>Regular</GlobalPurchaseOrderTypeCode>
    <OrderStatus>New</OrderStatus>
    <PurchaseOrderIdentifier>{{ order.order_number }}</PurchaseOrderIdentifier>
  </PurchaseOrder>
</Pip3A4PurchaseOrderRequest>
"""
            },

            # Odette OFTP2 (Automobilindustrie)
            {
                'name': 'Odette OFTP2 Global DELFOR',
                'code': 'odette_oftp2_delfor',
                'description': 'Odette OFTP2 DELFOR Standard für Lieferabrufe in der Automobilindustrie.',
                'industry': 'Automobilindustrie',
                'version': 'OFTP2',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<DELFOR>
  <HEADER>
    <SENDER>{{ order.company_id|default:"SENDERID" }}</SENDER>
    <RECEIVER>{{ supplier.id }}</RECEIVER>
    <DELFORNUM>{{ order.order_number }}</DELFORNUM>
    <DELFORDATE>{{ order.order_date|date:"Ymd" }}</DELFORDATE>
    <DELFORTIME>{{ order.order_date|date:"Hi" }}</DELFORTIME>
  </HEADER>
  <BUYER>
    <NAME>{{ order.company_name|default:"Ihre Firma GmbH" }}</NAME>
    <ADDRESS>{{ order.company_address|default:"" }}</ADDRESS>
  </BUYER>
  <SUPPLIER>
    <NAME>{{ supplier.name }}</NAME>
    <ID>{{ supplier.id }}</ID>
  </SUPPLIER>
  <SCHEDULE>
    {% for item in items %}
    <ITEM>
      <LINENUMBER>{{ forloop.counter }}</LINENUMBER>
      <PARTNUMBER>{{ item.supplier_sku }}</PARTNUMBER>
      <BUYERPARTNUMBER>{{ item.product.sku }}</BUYERPARTNUMBER>
      <DESCRIPTION>{{ item.product.name }}</DESCRIPTION>
      <QUANTITY>{{ item.quantity_ordered }}</QUANTITY>
      <UNITPRICE>{{ item.unit_price }}</UNITPRICE>
      <DELIVERYDATE>{{ order.delivery_date|date:"Ymd"|default:"" }}</DELIVERYDATE>
    </ITEM>
    {% endfor %}
  </SCHEDULE>
  <SUMMARY>
    <TOTALAMOUNT>{{ order.total }}</TOTALAMOUNT>
    <CURRENCY>EUR</CURRENCY>
    <ITEMCOUNT>{{ items|length }}</ITEMCOUNT>
  </SUMMARY>
</DELFOR>
"""
            },

            # Einfache XML-Struktur (für kleinere Unternehmen)
            {
                'name': 'Einfache XML-Bestellung',
                'code': 'simple_order',
                'description': 'Einfache XML-Struktur für Bestellungen, geeignet für kleinere Unternehmen und einfache Integrationsprojekte.',
                'industry': 'KMU, Allgemein',
                'version': '1.0',
                'template': """<?xml version="1.0" encoding="UTF-8"?>
<Bestellung>
  <Kopfdaten>
    <Bestellnummer>{{ order.order_number }}</Bestellnummer>
    <Bestelldatum>{{ order.order_date|date:"Y-m-d" }}</Bestelldatum>
    <Liefertermin>{{ order.delivery_date|date:"Y-m-d"|default:"" }}</Liefertermin>
  </Kopfdaten>

  <Besteller>
    <Firma>{{ order.company_name|default:"Ihre Firma GmbH" }}</Firma>
    <Ansprechpartner>{{ order.contact_name|default:"" }}</Ansprechpartner>
    <Email>{{ order.contact_email|default:"" }}</Email>
    <Telefon>{{ order.contact_phone|default:"" }}</Telefon>
  </Besteller>

  <Lieferant>
    <Name>{{ supplier.name }}</Name>
    <LieferantenNummer>{{ supplier.id }}</LieferantenNummer>
  </Lieferant>

  <Positionen>
    {% for item in items %}
    <Position>
      <Positionsnummer>{{ forloop.counter }}</Positionsnummer>
      <ArtikelNummer>{{ item.product.sku }}</ArtikelNummer>
      <LieferantenArtikelNummer>{{ item.supplier_sku }}</LieferantenArtikelNummer>
      <Beschreibung>{{ item.product.name }}</Beschreibung>
      <Menge>{{ item.quantity_ordered }}</Menge>
      <Einheit>Stück</Einheit>
      <Einzelpreis>{{ item.unit_price }}</Einzelpreis>
      <Gesamtpreis>{{ item.line_total }}</Gesamtpreis>
    </Position>
    {% endfor %}
  </Positionen>

  <Zusammenfassung>
    <Zwischensumme>{{ order.subtotal }}</Zwischensumme>
    <Steuer>{{ order.tax }}</Steuer>
    <Versandkosten>{{ order.shipping_cost }}</Versandkosten>
    <Gesamtbetrag>{{ order.total }}</Gesamtbetrag>
    <Waehrung>EUR</Waehrung>
  </Zusammenfassung>

  <Bemerkungen>{{ order.notes|default:"" }}</Bemerkungen>
</Bestellung>
"""
            }
        ]

        # Überprüfen, ob das XMLStandardTemplate-Modell existiert
        try:
            with transaction.atomic():
                # Zähler für die Statistik
                created_count = 0
                updated_count = 0

                for template_data in templates:
                    # Versuche, die Vorlage anhand des Codes zu finden oder zu erstellen
                    template, created = XMLStandardTemplate.objects.update_or_create(
                        code=template_data['code'],
                        defaults=template_data
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f"XML-Vorlage '{template.name}' erstellt"))
                    else:
                        updated_count += 1
                        self.stdout.write(self.style.WARNING(f"XML-Vorlage '{template.name}' aktualisiert"))

                self.stdout.write(self.style.SUCCESS(
                    f"Vorlagen-Initialisierung abgeschlossen: {created_count} erstellt, {updated_count} aktualisiert"
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fehler bei der Initialisierung: {str(e)}"))

            # Überprüfen, ob das Modell fehlt
            if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
                self.stdout.write(self.style.WARNING(
                    "Das XMLStandardTemplate-Modell scheint nicht zu existieren.\n"
                    "Bitte führen Sie zuerst folgende Schritte aus:\n"
                    "1. Fügen Sie das XMLStandardTemplate-Modell zu models.py hinzu\n"
                    "2. Führen Sie 'python manage.py makemigrations' aus\n"
                    "3. Führen Sie 'python manage.py migrate' aus\n"
                    "4. Führen Sie diesen Befehl erneut aus"
                ))