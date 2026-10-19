from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """Identifica somente a confirmação criada após um login bem-sucedido."""

    def add_message(
        self,
        request,
        level,
        message_template=None,
        message_context=None,
        extra_tags="",
        message=None,
    ):
        if message_template == "account/messages/logged_in.txt":
            extra_tags = f"{extra_tags} login-success".strip()
        return super().add_message(
            request,
            level,
            message_template,
            message_context,
            extra_tags,
            message,
        )
