from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.template import Context, Template
from django.utils import translation


def mail(fromaddr, addressees, subject, mailbody, replyto=None, extraattrs=None):
    if extraattrs is None:
        extraattrs = {}

    connection = get_connection(fail_silently=False)
    messages = []
    for addressee in addressees:
        if not addressee.email:
            continue

        attrs = {'addressee': addressee}
        attrs.update(extraattrs)

        # Try to translate the message to the users locale
        backup_language = None
        if hasattr(addressee, 'profile') and addressee.profile.current_language:
            backup_language = translation.get_language()
            translation.activate(addressee.profile.current_language)

        # Send message in both plain text and HTML, inserting linebreaks where required
        plain_text = Template(mailbody).render(Context(attrs))
        html_text = Template(mailbody).render(Context(attrs)).replace('\n', '<br>')

        # Revert locale back
        if backup_language:
            translation.activate(backup_language)

        msg = EmailMultiAlternatives(
            from_email=fromaddr,
            to=['%s <%s>' % (addressee.get_full_name(), addressee.email)],
            reply_to=replyto,
            subject=Template(subject).render(Context(attrs)),
            body=plain_text
        )
        msg.attach_alternative(html_text, 'text/html')
        messages.append(msg)

    connection.send_messages(messages)
