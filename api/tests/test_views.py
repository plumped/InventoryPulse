from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from accessmanagement.models import CustomPermission
from core.models import Product, Category, Tax


class ProductAPITest(APITestCase):
    def setUp(self):
        # Create test user with permissions
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password123')

        # Get the ContentType for the CustomPermission model
        content_type = ContentType.objects.get_for_model(CustomPermission)

        # Create necessary permissions
        self.view_permission = Permission.objects.get(
            codename='can_view_product',
            content_type=content_type
        )
        self.create_permission = Permission.objects.get(
            codename='can_create_product',
            content_type=content_type
        )

        # Assign permissions to user
        self.user.user_permissions.add(self.view_permission)
        self.user.user_permissions.add(self.create_permission)

        # Create test data
        self.category = Category.objects.create(name='Test Category')
        self.tax = Tax.objects.create(name='Standard', code='STD', rate=19.0)
        self.product = Product.objects.create(
            name='Test Product',
            sku='TP001',
            category=self.category,
            tax=self.tax,
            minimum_stock=10
        )

        # Create client and authenticate
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_product_list(self):
        """Test retrieving product list"""
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Assuming pagination is not enabled
        self.assertEqual(response.data[0]['name'], 'Test Product')

    def test_get_product_detail(self):
        """Test retrieving product detail"""
        url = reverse('product-detail', args=[self.product.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['sku'], 'TP001')
        self.assertEqual(response.data['category']['name'], 'Test Category')

    def test_create_product(self):
        """Test creating a new product"""
        url = reverse('product-list')
        data = {
            'name': 'New Product',
            'sku': 'NP001',
            'category': self.category.id,
            'tax': self.tax.id,
            'minimum_stock': 5,
            'unit': 'Piece'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Product.objects.get(sku='NP001').name, 'New Product')

    def test_update_product(self):
        """Test updating a product"""
        url = reverse('product-detail', args=[self.product.id])
        data = {
            'name': 'Updated Product',
            'sku': 'TP001',
            'category': self.category.id,
            'tax': self.tax.id,
            'minimum_stock': 15,
            'unit': 'Piece'
        }
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Updated Product')
        self.assertEqual(self.product.minimum_stock, 15)

    def test_delete_product(self):
        """Test deleting a product"""
        # First add delete permission
        content_type = ContentType.objects.get_for_model(CustomPermission)
        delete_permission = Permission.objects.get(
            codename='can_delete_product',
            content_type=content_type
        )
        self.user.user_permissions.add(delete_permission)

        url = reverse('product-detail', args=[self.product.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)


class CategoryAPITest(APITestCase):
    def setUp(self):
        # Create test user with permissions
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password123')

        # Get the ContentType for the CustomPermission model
        content_type = ContentType.objects.get_for_model(CustomPermission)

        # Create necessary permissions
        self.view_permission = Permission.objects.get(
            codename='can_view_product',
            content_type=content_type
        )

        # Assign permissions to user
        self.user.user_permissions.add(self.view_permission)

        # Create test data
        self.category = Category.objects.create(name='Test Category', description='Test Description')

        # Create client and authenticate
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_category_list(self):
        """Test retrieving category list"""
        url = reverse('category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Assuming pagination is not enabled
        self.assertEqual(response.data[0]['name'], 'Test Category')

    def test_get_category_detail(self):
        """Test retrieving category detail"""
        url = reverse('category-detail', args=[self.category.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Category')
        self.assertEqual(response.data['description'], 'Test Description')