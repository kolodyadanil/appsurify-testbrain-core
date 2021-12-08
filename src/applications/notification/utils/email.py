# -*- coding: utf-8 -*-
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from applications.notification.models import Notification
from applications.notification.utils.build_url import build_absolute_uri

TYPE_MAPPING = {
    Notification.TYPE_RISK: 'risk',
    Notification.TYPE_ALERT: 'alert',
    Notification.TYPE_DEFECT: 'defect',
    Notification.TYPE_TEST_RUN: 'test_run',
    Notification.TYPE_MONITOR: 'monitor',
    Notification.TYPE_TEST_PRIORITIZATION: 'test_prioritization',
    Notification.TYPE_RISK_ANALYSIS: 'risk_analysis',
}


def send_notification_email(notify, context=None):
    if context is None:
        context = {}

    context['domain'] = build_absolute_uri(notify.project.organization, '')
    try:
        type_notification = TYPE_MAPPING.get(notify.type)

        from_email = 'TestBrain Reports <noreply@appsurify.com>'

        subject = render_to_string('notification/email/email_{type}_subject.txt'.format(
            type=type_notification), context).strip()

        bodies = {}

        for ext in ['html', 'txt']:
            try:
                template_name = 'notification/email/email_{type}_message.{ext}'.format(type=type_notification, ext=ext)
                bodies[ext] = render_to_string(template_name, context).strip()
            except TemplateDoesNotExist:
                if ext == 'txt' and not bodies:
                    # We need at least one body
                    raise

        if 'txt' in bodies:
            msg = EmailMultiAlternatives(subject, bodies['txt'], from_email, [context['email']])
            if 'html' in bodies:
                msg.attach_alternative(bodies['html'], 'text/html')
        else:
            msg = EmailMessage(subject, bodies['html'], from_email, [context['email']])
            msg.content_subtype = 'html'  # Main content is now text/html

        msg.send()
        return True

    except Exception as e:
        print(e)
