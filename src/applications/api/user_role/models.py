from django.db import models


# Create your models here.
class UserRole(models.Model):
    name = models.CharField(max_length=255)
    index = models.IntegerField(default=99)

    def __str__(self):
        return self.name
