from django.test import TestCase

from master_data.models.tax_models import Tax
from product_management.models.categories_models import Category
from product_management.models.products_models import Product
from ..serializers import ProductListSerializer, ProductDetailSerializer, CategorySerializer


class CategorySerializerTest(TestCase):
    def setUp(self):
        self.category_data = {
            'name': 'Test Category',
            'description': 'Test Description'
        }
        self.category = Category.objects.create(**self.category_data)
        self.serializer = CategorySerializer(instance=self.category)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(set(data.keys()), set(['id', 'name', 'description']))

    def test_name_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['name'], self.category_data['name'])

    def test_description_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['description'], self.category_data['description'])


class ProductListSerializerTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Test Category')
        self.product_data = {
            'name': 'Test Product',
            'sku': 'TP001',
            'barcode': '1234567890',
            'category': self.category,
            'minimum_stock': 10
        }
        self.product = Product.objects.create(**self.product_data)
        self.serializer = ProductListSerializer(instance=self.product)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            set(['id', 'name', 'sku', 'barcode', 'category', 'category_name', 'minimum_stock'])
        )

    def test_category_name_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['category_name'], self.category.name)


class ProductDetailSerializerTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Test Category')
        self.tax = Tax.objects.create(name='Standard', code='STD', rate=19.0)
        self.product_data = {
            'name': 'Test Product',
            'sku': 'TP001',
            'barcode': '1234567890',
            'description': 'Test Description',
            'category': self.category,
            'tax': self.tax,
            'minimum_stock': 10,
            'unit': 'Piece',
            'has_variants': True,
            'has_serial_numbers': True,
            'has_batch_tracking': False,
            'has_expiry_tracking': False
        }
        self.product = Product.objects.create(**self.product_data)
        self.serializer = ProductDetailSerializer(instance=self.product)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            set([
                'id', 'name', 'sku', 'barcode', 'description', 'category', 'tax',
                'minimum_stock', 'unit', 'has_variants', 'has_serial_numbers',
                'has_batch_tracking', 'has_expiry_tracking', 'total_stock'
            ])
        )

    def test_nested_category_serialization(self):
        data = self.serializer.data
        self.assertEqual(data['category']['name'], self.category.name)

    def test_nested_tax_serialization(self):
        data = self.serializer.data
        self.assertEqual(data['tax']['name'], self.tax.name)
        self.assertEqual(data['tax']['rate'], self.tax.rate)