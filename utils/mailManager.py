class MailManager:
    def __init__(self):
        self.mails = {}  # {session_id: OpenAiService()}
        self.webhook = {}
        self.bgTask = {}
        self.killOwner = {}

    def set_kill_owner(self, userID):
        self.killOwner[userID] = True

    def get_kill_owner(self, userID):
        return self.killOwner.get(userID)

    def delete_kill_owner(self, userID):
        if userID in self.killOwner:
            del self.killOwner[userID]

    def set_user_mails(self, userID, mailCount):
        self.mails[userID] = mailCount

    # def set_user_hook(self, userID, Count):
    #     self.mails[userID] = Count
    def update_bg_task(self, userID):
        if userID in self.bgTask:
            self.bgTask[userID] += 1
        else:
            self.bgTask[userID] = 1

    def reduce_bg_task(self, userID):
        if userID in self.bgTask:
            self.bgTask[userID] -= 1

    def get_bg_task(self, userID):
        return self.bgTask.get(userID)

    def delete_user_mail(self, userID):
        if userID in self.mails:
            del self.mails[userID]

    def get_user_mails(self, userID):
        return self.mails.get(userID)

    def get_user_hook(self, userID):
        return self.webhook.get(userID)

    def reduce_user_mail(self, userID):
        if userID in self.mails:
            self.mails[userID] -= 1

    def delete_user_mail(self, userID):
        if userID in self.mails:
            del self.mails[userID]

    def delete_user_hook(self, userID):
        if userID in self.webhook:
            del self.webhook[userID]

    def delete_all_counts(self, userID):
        """Check if userID exists in webhook; increment if it does, set to 1 if it doesn't."""
        if userID in self.webhook:
            del self.webhook[userID]

        if userID in self.mails:
            del self.mails[userID]

    def update_webhook_count(self, userID):
        """Check if userID exists in webhook; increment if it does, set to 1 if it doesn't."""
        if userID in self.webhook:
            self.webhook[userID] += 1
        else:
            self.webhook[userID] = 1

    def compare_webhook_email(self, userID):
        """Compare webhook userID value with email userID value.
        Return True if they are the same, otherwise return False.
        """
        print("mail count in compare_webhook_email", self.mails.get(userID))
        print("hook count in compare_webhook_email", self.webhook.get(userID))
        return self.webhook.get(userID) == self.mails.get(userID)


mail_manager = MailManager()
