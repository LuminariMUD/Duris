#!/usr/bin/env python3
"""Login and registration show a brief notice; paged news is read on request."""

from _paths import extract_function, source

pages = extract_function("account.c", "void display_account_login_pages(")
password = extract_function("account.c", "static void finish_account_password(")
new_account = extract_function("account.c", "void verify_new_account_information(")

notice = "Type 'news' in game to read the latest updates."
motd = 'SEND_TO_Q(motd.c_str(), d);'
prompt = 'SEND_TO_Q("\\r\\n*** PRESS RETURN: ", d);'

assert notice in pages
assert "news.c_str()" not in source("account.c").read_text()
assert "news.c_str()" not in source("nanny.c").read_text()
assert motd in pages
assert prompt in pages
assert pages.index(notice) < pages.index(motd) < pages.index(prompt)
# Both ordinary and duplicate-session logins reach the same notice.
assert password.count("display_account_login_pages(d);") == 1
assert (password.index("close_socket(k);") < password.index("display_account_login_pages(d);")
        < password.index("STATE(d) = CON_ACCT_RMOTD;"))

# Registration uses the new account's descriptor. Verification-enabled
# registration hands off to the email challenge instead of the MOTD.
assert new_account.count("display_account_login_pages(") == 1
assert (new_account.index("if (account_recovery_enabled())")
        < new_account.index("begin_account_email_verification(reader,")
        < new_account.index("else")
        < new_account.index("display_account_login_pages(reader);")
        < new_account.index("STATE(reader) = CON_ACCT_RMOTD;"))
assert 'send_paged_text(recipient, display, LOG_NONE)' in extract_function("actinf.c", "void do_news(")

print("account login news regression passed")
