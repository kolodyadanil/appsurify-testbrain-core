# -*- coding: utf-8 -*-
from typing import List, Tuple, Optional, Union, AnyStr, Any
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.contrib.auth import password_validation
from django.core.mail import send_mail
from .exceptions import OrganizationOwnershipRequired, OrganizationOwnerAlreadyExists


ORGANIZATION_CACHE = {}


class UserManager(BaseUserManager):
    """
    Manager ORM class containing methods for creating a user object
    """
    use_in_migrations = True

    def _create_user(self, email: AnyStr, password: AnyStr, **extra_fields: Any) -> "User":
        """
        Create and save a user with the given email, and password.
        """
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(self, email: AnyStr, password: Optional[AnyStr] = None, **extra_fields: Any) -> "User":
        """ User.objects.create_user(email="normal@user.com", password="foo") -> <User: normal@user.com> """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: AnyStr, password: Optional[AnyStr] = None, **extra_fields: Any) -> "User":
        """ User.objects.create_superuser("super@user.com", "foo") -> <User: super@user.com> """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)

    def with_perm(self, perm, is_active=True, include_superusers=True, backend=None, obj=None):
        if backend is None:
            backends = auth._get_backends(return_tuples=True)
            if len(backends) == 1:
                backend, _ = backends[0]
            else:
                raise ValueError(
                    "You have multiple authentication backends configured and "
                    "therefore must provide the 'backend' argument."
                )
        elif not isinstance(backend, str):
            raise TypeError(
                "backend must be a dotted import path string (got %r)."
                % backend
            )
        else:
            backend = auth.load_backend(backend)
        if hasattr(backend, "with_perm"):
            return backend.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )
        return self.none()

    @classmethod
    def validate_password(cls, password: AnyStr) -> None:
        """
        If password valid, method return None or raise Exception.
        """
        password_validation.validate_password(password)
        return None


class User(AbstractBaseUser, PermissionsMixin):
    """
    Users within the Django authentication system are represented by this
    model.

    Email and password are required. Other fields are optional.

    An class implementing a fully featured User model with
    admin-compliant permissions.

    Email and password are required. Other fields are optional.
    """

    first_name = models.CharField(
        verbose_name="first name",
        max_length=255,
        blank=True,
        null=True
    )

    last_name = models.CharField(
        verbose_name="last name",
        max_length=255,
        blank=True,
        null=True
    )

    email = models.EmailField(
        verbose_name="email address",
        max_length=255,
        blank=False,
        null=False,
        unique=True,
        help_text="Required email address. Ex. mailbox@domain.tld",
    )

    is_staff = models.BooleanField(
        verbose_name="staff status",
        default=False,
        help_text="Designates whether the user can log into this admin site.",
    )

    is_active = models.BooleanField(
        verbose_name="active",
        default=True,
        help_text="Designates whether this user should be treated as active. "
                  "Unselect this instead of deleting accounts.",
    )

    date_joined = models.DateTimeField(
        verbose_name="date joined",
        auto_now_add=True,
        help_text="Auto-filled field user registered."
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email", ]
        verbose_name = "user"
        verbose_name_plural = "users"
        swappable = "AUTH_USER_MODEL"

    def __str__(self):
        return f"{self.email}"

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)


class OrganizationManager(models.Manager):
    use_in_migrations = True

    def _get_organization_by_id(self, organization_id):
        if organization_id not in ORGANIZATION_CACHE:
            organization = self.get(id=organization_id)
            ORGANIZATION_CACHE[organization_id] = organization
        return ORGANIZATION_CACHE[organization_id]

    def _get_organization_by_request(self, request):
        host = request.get_host().lower()
        try:
            if host not in ORGANIZATION_CACHE:
                if settings.PLATFORM == Organization.Platform.ON_PREMISES:
                    ORGANIZATION_CACHE[host] = self.first()
                else:
                    domain = host.split('.')[0]
                    ORGANIZATION_CACHE[host] = self.get(domain__iexact=domain)
        except Organization.DoesNotExist:
            ORGANIZATION_CACHE[host] = None
        return ORGANIZATION_CACHE[host]

    def clear_cache(self):
        """Clear the ``Organization`` object cache."""
        global ORGANIZATION_CACHE
        ORGANIZATION_CACHE = {}

    def get_by_natural_key(self, domain):
        return self.get(domain=domain)


class Organization(models.Model):
    """
    Default Organization model.
    """

    class Platform(models.TextChoices):
        SAAS = "saas", "SaaS"
        ON_PREMISES = "on-premises", "On-Premises"

    platform = models.CharField(
        verbose_name="platform",
        max_length=128,
        default=Platform.SAAS,
        choices=Platform.choices,
        blank=False,
        null=False
    )

    name = models.CharField(
        verbose_name="name",
        max_length=255,
        blank=False,
        null=False,
        unique=True
    )

    domain = models.CharField(
        verbose_name="domain",
        max_length=253,
        blank=False,
        null=False,
        unique=True,
        help_text="Auto-generated field"
    )

    users = models.ManyToManyField(
        User,
        verbose_name="users",
        through="OrganizationUser",
        related_name="organizations"
    )

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    objects = OrganizationManager()

    class Meta(object):
        ordering = ["name", ]
        verbose_name = "organization"
        verbose_name_plural = "organizations"

    def __str__(self):
        return f"{self.name}"

    @property
    def platform_display(self) -> AnyStr:
        return self.get_platform_display()

    @property
    def users_count(self) -> int:
        """ Return organization users count. """
        users_count = OrganizationUser.objects.filter(organization=self).count()
        return users_count

    def add_user(self, user: User, is_admin: bool = False, is_owner: bool = False) -> "OrganizationUser":
        """ Add user to organization and set user owner if users_count == 0. """
        if self.users_count == 0:
            is_admin = True
            is_owner = True

        org_user = OrganizationUser.objects.create(organization=self, user=user, is_admin=is_admin, is_owner=is_owner)
        return org_user

    def remove_user(self, user: User) -> None:
        org_user = OrganizationUser.objects.get(user=user)
        org_user.delete()

    def is_admin(self, user: User) -> bool:
        """
        Returns True is user is an admin in the organization, otherwise false
        """
        return True if self.organization_users.filter(user=user, is_admin=True) else False

    def is_owner(self, user: User) -> bool:
        """
        Returns True is user is the organization's owner, otherwise false
        """
        return True if self.organization_users.filter(user=user, is_owner=True) else False


class OrganizationUser(models.Model):
    """
    Default OrganizationUser model.
    """

    organization = models.ForeignKey(
        "Organization",
        related_name="organization_users",
        on_delete=models.CASCADE
    )

    user = models.ForeignKey(
        User,
        related_name="organization_users",
        on_delete=models.CASCADE
    )

    is_admin = models.BooleanField(default=False)

    is_owner = models.BooleanField(default=False)

    created = models.DateTimeField(
        verbose_name="created",
        auto_now_add=True,
        help_text="Auto-generated field"
    )

    updated = models.DateTimeField(
        verbose_name="updated",
        auto_now=True,
        help_text="Auto-generated and auto-updated field"
    )

    class Meta(object):
        ordering = ["organization", "user"]
        verbose_name = "organization user"
        verbose_name_plural = "organization users"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "is_owner"],
                condition=models.Q(is_owner=True),
                name="unique_organization_owner"
            ),
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_user"
            ),
        ]

    def __str__(self):
        return f"{self.organization} - {self.user}"

    def delete(self, using: Optional = None, keep_parents: bool = False) -> None:
        if self.is_owner:
            raise OrganizationOwnershipRequired("Cannot delete organization owner "
                                                "before organization or change ownership.")
        super().delete(using=using, keep_parents=keep_parents)


def clear_organization_cache(sender, **kwargs):
    """
    Clear the cache (if primed) each time a site is saved or deleted.
    """
    instance = kwargs['instance']
    using = kwargs['using']
    try:
        del ORGANIZATION_CACHE[instance.id]
    except KeyError:
        pass
    try:
        del ORGANIZATION_CACHE[Organization.objects.using(using).get(pk=instance.id).domain]
    except (KeyError, Organization.DoesNotExist):
        pass


pre_save.connect(clear_organization_cache, sender=Organization)
pre_delete.connect(clear_organization_cache, sender=Organization)
