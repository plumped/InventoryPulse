from django.contrib.auth.models import User
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_departments')
    members = models.ManyToManyField(User, related_name='departments')
    description = models.TextField(blank=True, verbose_name="Beschreibung")


    def __str__(self):
        return self.name
