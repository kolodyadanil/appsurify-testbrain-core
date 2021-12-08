# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.shortcuts import get_current_site
from django.http import (
    Http404,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.contrib.auth.tokens import default_token_generator

from rest_framework.response import Response
from django.core.signing import SignatureExpired, BadSignature
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth import login as django_login, logout as django_logout

from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings

from django.views.generic.edit import FormView
from .forms import AddEmailForm

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import (
    CreateAPIView,
    GenericAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
    UpdateAPIView,
    ListAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import exceptions
from . import app_settings, signals
from ..compat import (
    is_anonymous,
    is_authenticated,
    reverse,
    reverse_lazy,
    has_usable_password,
)
from ..exceptions import ImmediateHttpResponse
from ..utils import get_form_class, get_request_param
from .permissions import IsUnusablePassword
from .adapter import get_adapter
from .models import EmailAddress, EmailConfirmation, EmailConfirmationHMAC
from .utils import (
    complete_signup,
    get_login_redirect_url,
    get_next_redirect_url,
    logout_on_password_change,
    passthrough_next_redirect_url,
    perform_login,
    sync_user_email_addresses,
    url_str_to_user_pk,
    create_token,
)
from . import app_settings
from ..compat import reverse
from ..utils import (
    build_absolute_uri,
    get_username_max_length,
    set_form_field_order,
)


from rest_framework.authtoken.models import Token

from .serializers import (
    SignupSerializer,
    TokenSerializer,
    InviteSerializer,
    LoginSerializer,
    UserSerializer,
    UserDetailsSerializer,
    PasswordSetSerializer,
    OrganizationSignupSerializer,
    PasswordResetSerializer,
    OrganizationSignupV2Serializer,
)

from applications.allauth.socialaccount.models import SocialAccount, SocialApp
from applications.allauth.socialaccount import providers, adapter
from applications.allauth.utils import get_request_param
from applications.allauth.socialaccount.models import SocialApp

from applications.project import exceptions as ProjectExceptions
from applications.organization import exceptions as OrganizationExceptions
from applications.project.models import Project
from applications.organization.models import Organization, OrganizationUser
from applications.organization.utils import get_current_organization
from applications.organization.permissions import IsAdmin, IsOwner

from django.conf import settings

from django.core.exceptions import FieldError

from django.contrib.auth.models import User

INTERNAL_RESET_URL_KEY = "set-password"
INTERNAL_RESET_SESSION_KEY = "_password_reset_key"


sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("password", "password1", "password2")
)


def _ajax_response(request, response, form=None, data=None):
    if request.is_ajax():
        if isinstance(response, HttpResponseRedirect) or isinstance(
            response, HttpResponsePermanentRedirect
        ):
            redirect_to = response["Location"]
        else:
            redirect_to = None
        response = get_adapter(request).ajax_response(
            request, response, form=form, data=data, redirect_to=redirect_to
        )
    return response


class RedirectAuthenticatedUserMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if (
            is_authenticated(request.user)
            and app_settings.AUTHENTICATED_LOGIN_REDIRECTS
        ):
            redirect_to = self.get_authenticated_redirect_url()
            response = HttpResponseRedirect(redirect_to)
            return _ajax_response(request, response)
        else:
            response = super(RedirectAuthenticatedUserMixin, self).dispatch(
                request, *args, **kwargs
            )
        return response

    def get_authenticated_redirect_url(self):
        redirect_field_name = self.redirect_field_name
        return get_login_redirect_url(
            self.request,
            url=self.get_success_url(),
            redirect_field_name=redirect_field_name,
        )


class AjaxCapableProcessFormViewMixin(object):
    def get(self, request, *args, **kwargs):
        response = super(AjaxCapableProcessFormViewMixin, self).get(
            request, *args, **kwargs
        )
        form = self.get_form()
        return _ajax_response(
            self.request, response, form=form, data=self._get_ajax_data_if()
        )

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            response = self.form_valid(form)
        else:
            response = self.form_invalid(form)
        return _ajax_response(
            self.request, response, form=form, data=self._get_ajax_data_if()
        )

    def get_form(self, form_class=None):
        form = getattr(self, "_cached_form", None)
        if form is None:
            form = super(AjaxCapableProcessFormViewMixin, self).get_form(form_class)
            self._cached_form = form
        return form

    def _get_ajax_data_if(self):
        return self.get_ajax_data() if self.request.is_ajax() else None

    def get_ajax_data(self):
        return None


class CloseableSignupMixin(object):
    template_name_signup_closed = (
        "account/signup_closed." + app_settings.TEMPLATE_EXTENSION
    )

    def dispatch(self, request, *args, **kwargs):
        try:
            if not self.is_open():
                return self.closed()
        except ImmediateHttpResponse as e:
            return e.response
        return super(CloseableSignupMixin, self).dispatch(request, *args, **kwargs)

    def is_open(self):
        return get_adapter(self.request).is_open_for_signup(self.request)

    def closed(self):
        response_kwargs = {
            "request": self.request,
            "template": self.template_name_signup_closed,
        }
        return self.response_class(**response_kwargs)


class LoginAPIView(GenericAPIView):
    """"""

    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    token_model = Token

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(LoginAPIView, self).dispatch(*args, **kwargs)

    def process_login(self):
        # django_login(self.request, self.user)
        perform_login(
            self.request,
            self.user,
            email_verification=app_settings.EMAIL_VERIFICATION,
            redirect_url=None,
            signal_kwargs=None,
        )

    def get_response_serializer(self):
        response_serializer = TokenSerializer
        return response_serializer

    def login(self):
        self.user = self.serializer.validated_data["user"]
        self.token = create_token(self.token_model, self.user, self.serializer)
        self.process_login()

    def get_response(self):
        serializer_class = self.get_response_serializer()
        serializer = serializer_class(
            instance=self.token, context={"request": self.request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        self.request = request
        self.serializer = self.get_serializer(
            data=self.request.data, context={"request": request}
        )
        self.serializer.is_valid(raise_exception=True)
        self.login()
        return self.get_response()


login = LoginAPIView.as_view()


class LogoutAPIView(APIView):
    """"""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if app_settings.LOGOUT_ON_GET:
            response = self.logout(request)
        else:
            response = self.http_method_not_allowed(request, *args, **kwargs)
        return self.finalize_response(request, response, *args, **kwargs)

    def post(self, request):
        return self.logout(request)

    def logout(self, request):
        adapter = get_adapter(request)
        try:
            request.user.auth_token.delete()
        except (AttributeError, ObjectDoesNotExist):
            pass

        adapter.logout(request)
        return Response(
            {"detail": "Successfully logged out."}, status=status.HTTP_200_OK
        )
        # return (get_next_redirect_url(request, self.redirect_field_name) or
        #         adapter.get_logout_redirect_url(request))


logout = LogoutAPIView.as_view()


class OrganizationSignupAPIView(CreateAPIView):
    permission_classes = (AllowAny,)
    allowed_methods = ("POST", "OPTIONS", "HEAD")
    serializer_class = OrganizationSignupSerializer

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(OrganizationSignupAPIView, self).dispatch(*args, **kwargs)

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        organization = self.perform_create(serializer)

        if app_settings.LOGIN_ON_SIGNUP:
            perform_login(
                self.request,
                organization.owner.organization_user.user,
                email_verification=False,
                redirect_url=None,
                signal_kwargs=None,
                organization=organization,
            )

        headers = self.get_success_headers(serializer.data)
        return Response(data={}, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        organization = serializer.save(self.request)
        # if not organization:
        #     return None
        complete_signup(
            self.request._request,
            organization.owner.organization_user.user,
            app_settings.EMAIL_VERIFICATION,
            None,
            organization=organization,
        )

        return organization


signup = OrganizationSignupAPIView.as_view()


class OrganizationSignupV2APIView(CreateAPIView):
    permission_classes = (AllowAny,)
    allowed_methods = ("POST", "OPTIONS", "HEAD")
    serializer_class = OrganizationSignupV2Serializer

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(OrganizationSignupV2APIView, self).dispatch(*args, **kwargs)

    def login(self, user):
        adapter = get_adapter(self.request)
        try:
            adapter.logout(self.request)
        except Exception as exc:
            pass
        adapter.login(self.request, user)

    def get_response(self, user):
        token = create_token(Token, user)
        serializer_class = TokenSerializer
        serializer = serializer_class(instance=token, context={"request": self.request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # create djstripe customer
        user = get_user_model().objects.get(emailaddress__email=request.data["email"])
        # customer, created = Customer.get_or_create(subscriber=user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save()


signup_v2 = OrganizationSignupV2APIView.as_view()


class InviteAPIView(CreateAPIView):
    permission_classes = (
        IsAuthenticated,
        IsOwner,
        IsAdmin,
    )
    allowed_methods = ("POST", "OPTIONS", "HEAD")

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(InviteAPIView, self).dispatch(*args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        return InviteSerializer(*args, **kwargs)

    def get_response_data(self, user):
        return {"detail": "Verification e-mail sent."}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_response_data(user),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        create_token(Token, user, serializer)
        complete_signup(
            self.request._request,
            user,
            app_settings.EmailVerificationMethod.MANDATORY,
            success_url=None,
            signal_kwargs=None,
            organization=None,
        )
        return user


invite = InviteAPIView.as_view()


class ConfirmEmailAPIView(APIView):
    permission_classes = (AllowAny,)

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(ConfirmEmailAPIView, self).dispatch(*args, **kwargs)

    def login_on_confirm(self):
        """
        Simply logging in the user may become a security issue. If you
        do not take proper care (e.g. don't purge used email
        confirmations), a malicious person that got hold of the link
        will be able to login over and over again and the user is
        unable to do anything about it. Even restoring their own mailbox
        security will not help, as the links will still work. For
        password reset this is different, this mechanism works only as
        long as the attacker has access to the mailbox. If they no
        longer has access they cannot issue a password request and
        intercept it. Furthermore, all places where the links are
        listed (log files, but even Google Analytics) all of a sudden
        need to be secured. Purging the email confirmation once
        confirmed changes the behavior -- users will not be able to
        repeatedly confirm (in case they forgot that they already
        clicked the mail).

        All in all, opted for storing the user that is in the process
        of signing up in the session to avoid all of the above.  This
        may not 100% work in case the user closes the browser (and the
        session gets lost), but at least we're secure.
        """

        user = self.confirmation.email_address.user

        if not has_usable_password(user):
            return perform_login(
                self.request,
                user,
                app_settings.EmailVerificationMethod.NONE,
                redirect_url=None,
                signal_kwargs=None,
            )
        return None

    def confirm(self, request):
        if is_authenticated(request.user):
            django_logout(request)

        adapter = get_adapter(self.request)

        self.confirmation = self.get_object()

        if self.confirmation is None:
            return HttpResponseRedirect(self.get_redirect_url())

        self.confirmation.confirm(self.request)

        if app_settings.LOGIN_ON_EMAIL_CONFIRMATION:
            self.login_on_confirm()

        # TODO: clean confirmation token
        # self.confirmation.delete()
        return HttpResponseRedirect(self.get_redirect_url())

    def get(self, request, *args, **kwargs):
        if app_settings.CONFIRM_EMAIL_ON_GET:
            response = self.confirm(request)
        else:
            response = self.http_method_not_allowed(request, *args, **kwargs)
        return self.finalize_response(request, response, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = self.confirm(request)
        return self.finalize_response(request, response)

    def get_object(self):
        key = self.kwargs["key"]

        emailconfirmation = EmailConfirmationHMAC.from_key(key)
        if not emailconfirmation:
            queryset = self.get_queryset()
            try:
                emailconfirmation = queryset.get(key=key.lower())
            except EmailConfirmation.DoesNotExist:
                emailconfirmation = None
        return emailconfirmation

    def get_queryset(self):
        # qs = EmailConfirmation.objects.all_valid().exclude(email_address__verified=True)
        qs = EmailConfirmation.objects.all_valid()
        qs = qs.select_related("email_address__user")
        return qs

    def get_redirect_url(self):
        adapter = get_adapter(self.request)
        # TODO: IMPLEMENT CHECK IF UNAVAILABLE PASSEWORD!!!
        return adapter.get_email_confirmation_redirect_url(self.request)


confirm_email = ConfirmEmailAPIView.as_view()


class EmailView(AjaxCapableProcessFormViewMixin, FormView):
    template_name = "account/email." + app_settings.TEMPLATE_EXTENSION
    form_class = AddEmailForm
    success_url = reverse_lazy("account_email")

    def get_form_class(self):
        return get_form_class(app_settings.FORMS, "add_email", self.form_class)

    def dispatch(self, request, *args, **kwargs):
        sync_user_email_addresses(request.user)
        return super(EmailView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(EmailView, self).get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        email_address = form.save(self.request)
        get_adapter(self.request).add_message(
            self.request,
            messages.INFO,
            "account/messages/" "email_confirmation_sent.txt",
            {"email": form.cleaned_data["email"]},
        )
        signals.email_added.send(
            sender=self.request.user.__class__,
            request=self.request,
            user=self.request.user,
            email_address=email_address,
        )
        return super(EmailView, self).form_valid(form)

    def post(self, request, *args, **kwargs):
        res = None
        if "action_add" in request.POST:
            res = super(EmailView, self).post(request, *args, **kwargs)
        elif request.POST.get("email"):
            if "action_send" in request.POST:
                res = self._action_send(request)
            elif "action_remove" in request.POST:
                res = self._action_remove(request)
            elif "action_primary" in request.POST:
                res = self._action_primary(request)
            res = res or HttpResponseRedirect(self.success_url)
            # Given that we bypassed AjaxCapableProcessFormViewMixin,
            # we'll have to call invoke it manually...
            res = _ajax_response(request, res, data=self._get_ajax_data_if())
        else:
            # No email address selected
            res = HttpResponseRedirect(self.success_url)
            res = _ajax_response(request, res, data=self._get_ajax_data_if())
        return res

    def _action_send(self, request, *args, **kwargs):
        email = request.POST["email"]
        try:
            email_address = EmailAddress.objects.get(
                user=request.user,
                email=email,
            )
            get_adapter(request).add_message(
                request,
                messages.INFO,
                "account/messages/" "email_confirmation_sent.txt",
                {"email": email},
            )
            email_address.send_confirmation(request)
            return HttpResponseRedirect(self.get_success_url())
        except EmailAddress.DoesNotExist:
            pass

    def _action_remove(self, request, *args, **kwargs):
        email = request.POST["email"]
        try:
            email_address = EmailAddress.objects.get(user=request.user, email=email)
            if email_address.primary:
                get_adapter(request).add_message(
                    request,
                    messages.ERROR,
                    "account/messages/" "cannot_delete_primary_email.txt",
                    {"email": email},
                )
            else:
                email_address.delete()
                signals.email_removed.send(
                    sender=request.user.__class__,
                    request=request,
                    user=request.user,
                    email_address=email_address,
                )
                get_adapter(request).add_message(
                    request,
                    messages.SUCCESS,
                    "account/messages/email_deleted.txt",
                    {"email": email},
                )
                return HttpResponseRedirect(self.get_success_url())
        except EmailAddress.DoesNotExist:
            pass

    def _action_primary(self, request, *args, **kwargs):
        email = request.POST["email"]
        try:
            email_address = EmailAddress.objects.get_for_user(
                user=request.user, email=email
            )
            # Not primary=True -- Slightly different variation, don't
            # require verified unless moving from a verified
            # address. Ignore constraint if previous primary email
            # address is not verified.
            if (
                not email_address.verified
                and EmailAddress.objects.filter(
                    user=request.user, verified=True
                ).exists()
            ):
                get_adapter(request).add_message(
                    request,
                    messages.ERROR,
                    "account/messages/" "unverified_primary_email.txt",
                )
            else:
                # Sending the old primary address to the signal
                # adds a db query.
                try:
                    from_email_address = EmailAddress.objects.get(
                        user=request.user, primary=True
                    )
                except EmailAddress.DoesNotExist:
                    from_email_address = None
                email_address.set_as_primary()
                get_adapter(request).add_message(
                    request, messages.SUCCESS, "account/messages/primary_email_set.txt"
                )
                signals.email_changed.send(
                    sender=request.user.__class__,
                    request=request,
                    user=request.user,
                    from_email_address=from_email_address,
                    to_email_address=email_address,
                )
                return HttpResponseRedirect(self.get_success_url())
        except EmailAddress.DoesNotExist:
            pass

    def get_context_data(self, **kwargs):
        ret = super(EmailView, self).get_context_data(**kwargs)
        # NOTE: For backwards compatibility
        ret["add_email_form"] = ret.get("form")
        # (end NOTE)
        return ret

    def get_ajax_data(self):
        data = []
        for emailaddress in self.request.user.emailaddress_set.all():
            data.append(
                {
                    "id": emailaddress.pk,
                    "email": emailaddress.email,
                    "verified": emailaddress.verified,
                    "primary": emailaddress.primary,
                }
            )
        return data


email = login_required(EmailView.as_view())


class PasswordSetAPIView(CreateAPIView):
    serializer_class = PasswordSetSerializer
    # success_url = reverse_lazy('account_set_password,')
    permission_classes = (IsAuthenticated,)
    allowed_methods = ("POST", "OPTIONS", "HEAD")

    @sensitive_post_parameters_m
    def dispatch(self, request, *args, **kwargs):
        return super(PasswordSetAPIView, self).dispatch(request, *args, **kwargs)

    def get_response_data(self, user):
        return {}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_response_data(user),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        logout_on_password_change(self.request, user)
        signals.password_set.send(
            sender=user.__class__, request=self.request, user=user
        )
        return user


password_set = PasswordSetAPIView.as_view()


class PasswordResetAPIView(CreateAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = (AllowAny,)

    def get_response_data(self, *args, **kwargs):
        return {"detail": "Verification e-mail sent."}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        email = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_response_data(email),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        email = serializer.save(self.request)
        # logout_on_password_change(self.request, user)
        # signals.password_set.send(sender=user.__class__, request=self.request, user=user)
        return email


password_reset = PasswordResetAPIView.as_view()


class PasswordResetFromKeyAPIView(APIView):
    permission_classes = (AllowAny,)

    uidb36 = None
    key = None

    reset_user = None
    token_generator = default_token_generator
    error_messages = {"token_invalid": "The password reset token was invalid."}

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(PasswordResetFromKeyAPIView, self).dispatch(*args, **kwargs)

    def get_object(self):
        uidb36 = self.kwargs.pop("uidb36")
        User = get_user_model()
        try:
            pk = url_str_to_user_pk(uidb36)
            return User.objects.get(pk=pk)
        except (ValueError, User.DoesNotExist):
            return None

    def get_queryset(self):
        qs = User.objects.none()
        return qs

    def get_redirect_url(self):
        adapter = get_adapter(self.request)
        redirect_url = adapter.get_reset_password_confirmation_redirect_url(
            self.request
        )
        return redirect_url

    def confirm(self, request):

        if is_authenticated(request.user):
            django_logout(request)

        adapter = get_adapter(self.request)

        key = self.kwargs.pop("key")

        reset_user = self.get_object()

        if reset_user is None or not self.token_generator.check_token(reset_user, key):
            return HttpResponseRedirect(self.get_redirect_url())

        adapter.login(request, reset_user)
        return HttpResponseRedirect(self.get_redirect_url())

    def get(self, request, *args, **kwargs):
        response = self.confirm(request)
        return self.finalize_response(request, response, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = self.confirm(request)
        return self.finalize_response(request, response)


password_reset_from_key = PasswordResetFromKeyAPIView.as_view()


class UserDetailsView(RetrieveUpdateAPIView):
    """
    Reads and updates UserModel fields
    Accepts GET, PUT, PATCH methods.

    Default accepted fields: username, first_name, last_name
    Default display fields: pk, username, email, first_name, last_name
    Read-only fields: pk, email

    Returns UserModel fields.
    """

    serializer_class = UserDetailsSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def get_queryset(self):
        """
        Adding this method since it is sometimes called when using
        django-rest-swagger
        https://github.com/Tivix/django-rest-auth/issues/275
        """
        return get_user_model().objects.none()


user_detail = UserDetailsView.as_view()


class UserProfileView(RetrieveUpdateAPIView):
    """
    Reads and updates UserModel fields
    Accepts GET, PUT, PATCH methods.

    Default accepted fields: username, first_name, last_name
    Default display fields: pk, username, email, first_name, last_name
    Read-only fields: pk, email

    Returns UserModel fields.
    """

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        try:
            return self.request.user
        except Exception as e:
            return None

    def get_queryset(self):
        """
        Adding this method since it is sometimes called when using
        django-rest-swagger
        https://github.com/Tivix/django-rest-auth/issues/275
        """
        return User.objects.none()


user_profile = UserProfileView.as_view()


class UserListCreateView(ListCreateAPIView):
    """
    View to list all users in the system or create new user.

    * Requires token authentication.
    * Only admin users are able to access this view.
    """

    queryset = get_user_model().objects.all()

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    ordering_fields = "__all__"
    search_fields = ("username",)
    filter_fields = ()

    def get_organization(self):
        organization = get_current_organization(request=self.request)
        return organization

    def get_queryset(self):
        queryset = super(UserListCreateView, self).get_queryset()
        user = self.request.user

        if not user.is_superuser:
            organization = get_current_organization(request=self.request)
            # assert organization is not None, 'Organization not found.'
            if organization is not None:
                queryset = queryset.filter(organization_organization=organization)
            else:
                queryset = queryset.none()
        return queryset

    def perform_create(self, serializer):
        user = get_user_model().objects.create_user(
            username=serializer.data.get("username", ""),
            email=serializer.data.get("email", ""),
            password=serializer.data.get("password", ""),
        )

        organization = self.get_organization()
        organization.add_user(user=user, is_admin=False)

        data = self.get_serializer(
            user, fields=("id", "username", "email", "password")
        ).data
        return data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user_data = self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(user_data, status=status.HTTP_201_CREATED, headers=headers)


user_list = UserListCreateView.as_view()


class UserRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    """
    View for retrieve, update or destroy user instance.

    * Requires token authentication.
    * Only admin users are able to access this view.
    """

    queryset = get_user_model().objects.all()

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            with transaction.atomic():
                current_organization = get_current_organization(request)
                current_organization.remove_user(instance)

                projects = Project.objects.get_for_user(instance).filter(
                    organization=current_organization
                )
                for project in projects:
                    project.remove_user(instance)

                organizations = Organization.objects.get_for_user(instance)
                if not organizations.exists():
                    self.perform_destroy(instance)

        except OrganizationExceptions.OwnershipRequired as e:
            return Response(
                {"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except ProjectExceptions.OwnershipRequired as e:
            return Response(
                {"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except OrganizationUser.DoesNotExist as e:
            return Response(
                {"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()


user_retrieve = UserRetrieveUpdateDestroyView.as_view()


class ProviderLoginURLNode(object):
    def __init__(self, request, provider_id, **kwargs):
        self.request = request
        self.provider_id = provider_id
        self.params = kwargs

    def build_url(self):
        provider = providers.registry.by_id(self.provider_id, self.request)

        query = self.params

        auth_params = query.get("auth_params", None)
        scope = query.get("scope", None)
        process = query.get("process", None)

        if scope == "":
            del query["scope"]

        if auth_params == "":
            del query["auth_params"]

        if "next" not in query:
            next = get_request_param(self.request, "next")

            if next:
                query["next"] = next
            elif process == "redirect":
                query["next"] = self.request.get_full_path()

        else:
            if not query["next"]:
                del query["next"]
        # get the login url and append query as url parameters
        return provider.get_login_url(self.request, **query)


def provider_login_url(request, provider_id, **kwargs):
    login_url = ProviderLoginURLNode(request, provider_id, **kwargs)
    return login_url


@api_view(["GET"])
def social_application_list(request):
    from django.contrib.sites.models import Site

    data = dict()
    results = list()
    next_url = getattr(settings, "SOCIALACCOUNT_REDIRECT_URL", "/")

    if hasattr(settings, "SITE_ID"):
        try:
            site = Site.objects.get(id=settings.SITE_ID)
        except Site.DoesNotExist:
            site = Site.objects.last()
    else:
        site = get_current_site(request)

    social_apps = SocialApp.objects.filter(sites__id=site.id)

    for social_app in social_apps:
        provider = providers.registry.by_id(social_app.provider, request)
        provider_url = provider_login_url(
            request,
            provider.id,
            process="connect",
            scope="",
            auth_params="",
            next=next_url,
        ).build_url()

        results.append(
            dict(
                name=social_app.name,
                provider_id=provider.id,
                provider_name=provider.name,
                provider_url="{0}://{1}{2}".format(
                    app_settings.DEFAULT_HTTP_PROTOCOL, request.get_host(), provider_url
                ),
            )
        )

    data = dict(results=results, count=len(results))
    return Response(data, status=status.HTTP_200_OK)


class CheckUsername(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        username = request.query_params.get("username", None)

        user_model = get_user_model()

        try:
            user_model.objects.get(username=username)
            return Response({"exists": True}, status=status.HTTP_200_OK)
        except user_model.DoesNotExist:
            return Response({"exists": False}, status=status.HTTP_200_OK)


check_username = CheckUsername.as_view()


class CheckUserEmail(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        email = request.query_params.get("email", None)

        user_model = get_user_model()

        try:
            user_model.objects.get(email=email)
            return Response({"exists": True}, status=status.HTTP_200_OK)
        except user_model.DoesNotExist:
            return Response({"exists": False}, status=status.HTTP_200_OK)


check_user_email = CheckUserEmail.as_view()


class CheckUserPassword(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        username = request.query_params.get("username", None)
        password = request.query_params.get("password", None)
        user = User(username=username)

        try:
            validate_password(password, user=user)
            return Response({"valid": True, "errors": []}, status=status.HTTP_200_OK)
        except ValidationError as errors:
            formatted_errors = []

            for error in errors:
                formatted_errors.append(error.encode("utf-8"))

            return Response(
                {"valid": False, "errors": formatted_errors}, status=status.HTTP_200_OK
            )


check_user_password = CheckUserPassword.as_view()
