# Dawesville Weekend Bot

Every Thursday at about 6:45pm (Perth time), your iPhone texts the family group chat something like:

> Dawesville Weekend Assessment
>
> • 18–19° and dry, light winds Saturday morning<br>
> • Herring and tailor biting at the Cut; crabbing still closed 🎣<br>
> • New cafe open in Falcon, or Peel Produce Market Sat morning<br>
> Dawesville weekend: 7/10

## How it works

```
Thursday 9:23am   GitHub (free) runs weekend_bot.py:
                    1. gets the Dawesville forecast (Open-Meteo, free)
                    2. checks WA long weekends + school holidays (built-in list)
                    3. asks Claude to search what's on nearby and write the message
                    4. saves it to latest.json in your GitHub repo
...then hourly    Retries until 5:23pm, because GitHub's timer sometimes skips runs
                  (once today's message is written, the retries do nothing)
Thursday 3:00pm   Backup: your iPhone tells GitHub to run it too (Step 6), in case
                  GitHub's timer skipped every try
Thursday 6:45pm   Your iPhone Shortcut reads latest.json and sends it to the family chat
Other days        GitHub's timer runs once at 11:23am as a free health check (writes nothing)
```

The iPhone does the sending, so the message comes from your own Apple account. Your PC doesn't
need to be on. Your family's phone numbers stay on your phone and never go to GitHub.

**Safety check:** the Shortcut only sends if the message is dated today. If something breaks,
the family gets nothing (never last week's message) and you get a notification instead
(row 8 of Step 4).

**Cost:** GitHub and the weather are free. Claude costs roughly US$0.25–0.60 per message
(about A$1.50–4 a month). The Claude account needs at least US$5 of credit to start, which
should last a few months. That's an estimate, so check the real cost after the first run
(console.anthropic.com → Usage).

---

## Setup (about 30 minutes, one time)

### Step 1: Put the bot on GitHub

1. Make a free account at https://github.com if you don't have one.
2. Click **+** (top right) → **New repository**. Name it `dawesville-weekend-bot`, choose
   **Public**, and **don't** tick "Add a README". Click **Create repository**.
   (It has to be public so your iPhone can read the message without a password. Anyone who
   finds it only sees weather and event messages, nothing personal.)
3. In PowerShell, run these (put your GitHub username in the first one):

```bash
cd C:\Users\Wenry\Downloads\dawesville-weekend-bot
git remote add origin https://github.com/YOUR-USERNAME/dawesville-weekend-bot.git
git push -u origin main
```

   A browser window will pop up asking you to log in to GitHub. That's normal.

### Step 2: Get a Claude API key and give it to GitHub

1. Go to https://console.anthropic.com, sign up, and add US$5 of credit under **Billing**.
   (This is separate from your Claude app subscription.)
2. Go to **API Keys** → **Create Key**, name it `weekend-bot`, and copy it.
3. On GitHub, open your repo → **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret**. Name: `ANTHROPIC_API_KEY`. Secret: paste the key. **Add secret**.
   GitHub keeps it hidden, so it never appears in your code.

### Step 3: Test it

1. On GitHub, open your repo → **Actions** tab → **Weekly Dawesville message** (left side) →
   **Run workflow** → **Run workflow**.
2. Wait 1–3 minutes until it shows a green tick. Click into it to see the message in the log.
3. Your repo now has a `latest.json` file. Open this in your phone's browser to check it works:
   `https://raw.githubusercontent.com/YOUR-USERNAME/dawesville-weekend-bot/main/latest.json`

If it shows a red cross, click into it and read the error. The usual cause is a mistyped secret name.

### Step 4: Build the iPhone Shortcut

Open the **Shortcuts** app → **Shortcuts** tab → **+**. Name it **Dawesville Weekend**.
Add these actions in order (use the search bar at the bottom to find each one):

| # | Action | How to set it |
|---|--------|---------------|
| 1 | **Get Contents of URL** | Paste your **raw** URL from Step 3 (starts with `https://raw.githubusercontent.com/`, not `https://github.com/`) |
| 2 | **Get Dictionary from Input** | Leave as is (it uses "Contents of URL") |
| 3 | **Get Dictionary Value** | Tap the word **Key** and type `for_date`. The last bubble must be **Dictionary** (from #2) |
| 4 | **Format Date** | The date bubble must be **Current Date** (today), not Dictionary Value. Tap the arrow → Date Format: **Custom** → type `yyyy-MM-dd` |
| 5 | **If** | Input: **Dictionary Value** (from #3) · Condition: **is** · Text: **Formatted Date** (from #4) |
| 6 | **Get Dictionary Value** *(inside the If)* | Tap the word **Key** and type `message`. Last bubble: tap it → **Clear** → tap again → **Select Variable** → tap action #2 |
| 7 | **Send Message** *(inside the If)* | Message bubble: **Clear** → **Select Variable** → tap action #6. Recipients: see below. Tap the arrow and turn **Show When Run** OFF |
| 8 | **If** *(below End If)* | Input: tap → **Select Variable** → action #3 · Condition: **is not** · Text: **Formatted Date**. Inside it add **Show Notification**: `Weekend bot: no fresh message - run it on GitHub` |

**Tip:** never type into an orange bubble. That renames it instead of setting the key. Keys go
in the plain blue **Key** word.

**Choosing the group chat:** in **Send Message**, tap **Recipients** and add **every person in
the family chat**. Use the same number or email the group uses for each person, and don't
include yourself. Messages sends it into the existing chat with exactly those people. If
Shortcuts suggests the group by name, you can pick that instead.

**Test it on yourself first:** set Recipients to just yourself, run the Shortcut (▶), and check the
text arrives. Only then swap the recipients to the family. (It only sends on a day when
`latest.json` is dated today, so do Step 3 again first if needed.)

### Step 5: Make it run every Thursday

Shortcuts app → **Automation** tab → **+** → **Time of Day** →
- Time: **6:45 PM**, Repeat: **Weekly**, only **Thursday** ticked
- Choose **Run Immediately** (not "Run After Confirmation")
- **Next** → pick **Dawesville Weekend** → **Done**

Your phone needs to be on with signal or Wi-Fi at 6:45pm. It should work while locked, but watch
the first Thursday to make sure.

**Optional preview:** make a second automation at 6:00pm that runs a tiny shortcut
(Get Contents of URL → Get Dictionary Value `message` → Show Notification). You then have 45
minutes to switch off the 6:45 automation that week if you don't like the message.

### Step 6: Backup start from your phone (recommended)

GitHub's timer is "best effort" and has skipped runs before. This makes your phone start the
run itself on Thursday afternoons. If GitHub already wrote the message, this run does nothing
and costs nothing.

**6a. Make a GitHub token** (a limited password that can only start this bot):
1. On GitHub, tap your profile picture → **Settings** → **Developer settings** (bottom of the
   left menu) → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. Name: `weekend-bot-phone`. Expiration: the longest it offers. Put a reminder in your
   calendar to make a new one when it runs out.
3. Repository access: **Only select repositories** → `dawesville-weekend-bot`.
4. Permissions: find **Actions** and set it to **Read and write**. Leave everything else.
5. **Generate token** and copy it. It's only shown once. Don't share it with anyone.

**6b. Make a shortcut called `Wake Weekend Bot`** with one action, **Get Contents of URL**:
- URL: `https://api.github.com/repos/YOUR-USERNAME/dawesville-weekend-bot/actions/workflows/weekly-message.yml/dispatches`
- Tap the arrow to show more options:
  - Method: **POST**
  - Headers: add `Authorization` = `Bearer ` followed by your token (with a space after Bearer),
    and add `Accept` = `application/vnd.github+json`
  - Request Body: **JSON** → add a **Text** field: key `ref`, value `main`

Press ▶ to test it. Nothing pops up on the phone, but within a minute a new run appears in
GitHub's **Actions** tab. (Test it on a Thursday evening after the message is sent and it
costs nothing. On other days the test writes a spare message, about US$0.50.) If no run
appears, add a **Show Result** action under it and press ▶ again to see GitHub's reply:
"Bad credentials" means the token was pasted wrong; "Not Found" or "Resource not accessible"
means the URL is wrong or the token doesn't have **Actions: Read and write**.

**6c. Automation:** Automation tab → **+** → **Time of Day** → **3:00 PM**, Weekly, Thursday only
→ **Run Immediately** → pick **Wake Weekend Bot** → **Done**.

---

## Changing things

- **The tone or what it looks for:** edit `SYSTEM_PROMPT` in `weekend_bot.py` (it's plain English).
- **The send time:** change the Shortcuts automation. If you move it earlier than 5:30pm, also
  make the GitHub runs earlier (the `cron` lines in `.github/workflows/weekly-message.yml`; GitHub
  uses UTC, which is Perth time minus 8 hours).
- **A message you don't like:** GitHub → Actions → Run workflow, tick **Replace today's
  message**, then Run workflow. Without the tick, it only writes one if today's is missing.
- **Every year:** the WA public holiday and school holiday lists in `weekend_bot.py` run out at
  the end of 2027. Until they're updated, the bot looks those dates up itself.

After changing a file on your PC, save it to GitHub with:

```bash
git commit -am "Tweak the bot"
```

```bash
git push
```

## Running it on your PC (optional)

```bash
.venv\Scripts\python weekend_bot.py --facts-only
```

This shows the weather and holiday facts the bot would use. It's free and needs no key. `--dry-run`
writes a real message without saving it, but it needs your API key set in PowerShell first
(`$env:ANTHROPIC_API_KEY = "..."`).
