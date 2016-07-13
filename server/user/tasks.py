from datetime import datetime, timedelta
import sendgrid

from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from cornerwise import celery_app
from cornerwise.utils import make_absolute_url

from .models import Subscription, UserProfile
from .changes import find_updates
# from proposal.models import Proposal
# from proposal.query import build_proposal_query

logger = get_task_logger(__name__)


if getattr(settings, "SENDGRID_API_KEY", None):
    SG = sendgrid.SendGridClient(settings.SENDGRID_API_KEY,
                                 raise_errors=True)
else:
    SG = None


def has_name(u):
    return u.first_name and u.last_name


def send_mail(user, subject, template_name, context={}):
    context = context.copy()
    context["user"] = user
    context["profile"] = user.profile
    html = render_to_string("email/" + template_name + ".djhtml", context)
    try:
        text = render_to_string("email/" + template_name + ".djtxt", context)
    except TemplateDoesNotExist:
        text = strip_tags(html)

    if SG:
        message = sendgrid.Mail(
            subject=subject,
            html=html,
            text=text,
            from_email=settings.EMAIL_ADDRESS)
        if has_name(user):
            message.add_to("{first} {last} <{email}>".
                           format(first=user.first_name,
                                  last=user.last_name,
                                  email=user.email))
        else:
            message.add_to(user.email)
        status, msg = SG.send(message)
        logger.info("Sent '%s' email to %s (status %i)",
                    template_name, user.email, status)
    else:
        logger.info("SendGrid not available. Generated email: %s", html)


@celery_app.task()
def send_subscription_updates(user_id, updates):
    user = User.objects.get(pk=user_id)
    send_mail(user, "Cornerwise: New Updates",
              "updates", {})


@celery_app.task(name="user.send_user_key")
def send_user_key(user_id):
    profile = UserProfile.objects.get(user_id=user_id)
    if not profile.token:
        profile.generate_token()

    # Render HTML and text templates:
    context = {"confirm_url": make_absolute_url(profile.manage_url)}
    send_mail(profile.user, "Cornerwise: Please confirm your email",
              "confirm", context)


@celery_app.task(name="user.resend_user_key")
def resend_user_key(user_id):
    profile = UserProfile.objects.get(user_id=user_id)
    if not profile.token:
        profile.generate_token()

    send_mail(profile.user, "Cornerwise: Your Account",
              "login_link", { "user": profile.user })


@celery_app.task()
def send_deactivation_email(user_id):
    user = User.objects.get(pk=user_id)
    send_mail(user, "Cornerwise: Account Disabled", "account_deactivated")


@celery_app.task()
def send_reset_email(user_id):
    user = User.objects.get(pk=user_id)
    send_mail(user, "Cornerwise: Login Reset", "account_reset")


@celery_app.task(name="user.send_notifications")
def send_notifications(subscription_ids=None, since=None):
    """Check the Subscriptions and find those that have new updates since the last
    update was run.
    """
    if subscription_ids is None:
        subscriptions = Subscription.objects.all()
    else:
        subscriptions = Subscription.objects.filter(pk__in=subscription_ids)

    if since is None:
        since = datetime.now() - timedelta(days=7)

    for subscription in subscriptions:
        updates = find_updates(subscription, since)
        if updates:
            send_subscription_updates(subscription.user, updates)


# Database hooks:
def user_profile_created(**kwargs):
    if kwargs["created"]:
        profile = kwargs["instance"]
        send_user_key.delay(profile.user_id)


def set_up_hooks():
    post_save.connect(user_profile_created, UserProfile,
                      dispatch_uid="send_confirmation_email")
