# Account email and password recovery

## Players

If you can log in, use account-menu option **5** on telnet, or **Account → Email** in
the browser client. Enter an inbox you control, then enter the verification code from
that inbox. This also lets you verify your existing address or add a missing one.
Your recovery address stays unchanged until verification succeeds. New accounts created
with mail enabled have no recovery address until this step is complete. You can still
play while verification is pending; return to the account menu to finish later.

If you forgot your password, enter your account name and type **?** at the telnet
password prompt. In the browser client choose **Forgot password?** on the login panel.
Request the code, read the email, enter the code and choose a new password, then log in.
The website login uses the same account password and links to the browser recovery form.
Recovery changes the password; it never retrieves the old one.

Codes work once, expire after 15 minutes, and are lost when the game restarts or copies
over. Request a new code after a restart. Each account can request one code of each kind
per 10 minutes, and each client address can request five codes in 10 minutes. Five wrong
guesses exhaust a code. Check spam if nothing arrives. A request response intentionally
does not reveal whether an account or usable email exists. If delivery fails, wait and
retry or ask staff. If storage fails, use the same code while it is still valid.

## Staff fallback

Players who can log in can verify a new inbox without access to the previous inbox.
A locked-out player who cannot access their registered inbox needs staff help. Use the
established manual account-ownership checks; do not treat knowledge of an email address
or a claimed character name as proof. Do not disclose the registered address, password
hash, or codes. Once ownership is established, use the authorized account administration
procedure to restore access, then have the player verify their current inbox and choose
a unique password. Staff must never ask a player for their mailbox password.

If delivery is unavailable, the account-menu and reset paths say so. Escalate repeated
delivery failures using the numeric curl/SMTP outcomes in the operational logs, without
copying addresses, codes, credentials or raw SMTP conversations into reports.

## Prepare activation without rebooting

1. Configure `MAIL_ENABLED=TRUE`, `MAIL_HOST`, `MAIL_FROM` and relay credentials in the
   private environment file, with `MAIL_TLS=TRUE`. Use a provider-authorized sender.
   See [the configuration contract](CONFIGURATION.md#account-recovery-mail) for the full
   validation and shell-safety rules. Check that inherited launcher environment values
   will not override the intended file values. Settings are read once at startup.
2. Build the MUD and browser client and run the focused tests in
   [TESTING.md](../guides/TESTING.md#account-recovery-contracts). Keep the current game
   and website running. Stage browser output away from the live `frontend/dist` tree.
3. Send authorized tests through the real configured relay, require TLS and confirm
   actual inbox delivery. SMTP 250 alone does not prove inbox receipt. Inspect sender
   authentication results where available. Use disposable accounts and an isolated
   database to test registration, inbox verification, reset, single use and old/new
   password login on telnet and WebSocket without restarting the production game.
4. Stage the qualified MUD executable with its `mariadb/production` stamp and retain
   the browser build, source revisions, validation and rollback evidence privately.
   This feature requires no schema migration. Publish player help and browser assets
   at the planned activation boundary, then perform the separately authorized reboot.
5. After that reboot, require the enabled startup log, perform the production smoke
   journey on both clients with an authorized account/inbox, and verify public health.
   Do not mark the issue's production activation accepted before these checks.

Optional password/email-change notifications and marketing mail are separate work.
Account recovery and verification never opt a player into announcements.
