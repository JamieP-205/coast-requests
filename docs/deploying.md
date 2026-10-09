# Deploying to PythonAnywhere

The app runs on a free PythonAnywhere account. Netlify sends each song request
from coastinternetradio.com to it as a signed webhook.

Replace `USERNAME` below with your PythonAnywhere username.

## 1. Put the code on PythonAnywhere

Open a **Bash console** on PythonAnywhere and run:

```bash
git clone https://github.com/JamieP-205/coast-requests.git
cd coast-requests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Add the settings

Still in the console, make two random secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"   # for SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"   # for NETLIFY_WEBHOOK_SECRET
```

Create `.env` in the `coast-requests` folder (`nano .env`) with them:

```
SECRET_KEY=<first value>
ADMIN_USERNAME=coastadmin
NETLIFY_WEBHOOK_SECRET=<second value>
```

Then make the hash of Jim's password, and add it to `.env` as a fourth line,
`ADMIN_PASSWORD_HASH=<the hash>`:

```bash
flask --app coast_requests hash-password
```

`.env` is in `.gitignore`, so it never goes to GitHub.

## 3. Create the web app

On the **Web** tab:

1. **Add a new web app**, choose **Manual configuration** and the newest Python.
2. Under **Virtualenv**, enter `/home/USERNAME/coast-requests/.venv`.
3. Open the **WSGI configuration file** link, delete everything in it and put:

   ```python
   import sys

   path = "/home/USERNAME/coast-requests"
   if path not in sys.path:
       sys.path.insert(0, path)

   from wsgi import application  # noqa: E402,F401
   ```

4. Under **Static files**, add URL `/static/` with directory
   `/home/USERNAME/coast-requests/coast_requests/static`.
5. Turn on **Force HTTPS**.
6. Press **Reload**, then open `https://USERNAME.pythonanywhere.com` and sign in.

## 4. Send requests from Netlify

In Netlify, open **coast-rebuild**, then **Forms**, **Form notifications**,
**Add notification**, **Outgoing webhook**:

- **Event to listen for:** New form submission
- **URL to notify:** `https://USERNAME.pythonanywhere.com/webhook/netlify`
- **Form:** `song-request`
- **JWS secret token:** the same `NETLIFY_WEBHOOK_SECRET` as in `.env`

Send a test request from coastinternetradio.com. It should appear on the board
within 20 seconds, and still arrive by email as before.

## Keeping it running

- Free web apps stop after a month unless you press **Run until 1 month from
  today** on the Web tab. PythonAnywhere emails a reminder first.
- To update: `cd coast-requests && git pull`, then **Reload** on the Web tab.
- The database is `instance/requests.db`. Download it from the **Files** tab
  for a backup.
