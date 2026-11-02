# Alexa

Ask about and change the inventory by voice:

- "Alexa, tell Home Inventory to add blueberries to the list"
- "Alexa, ask Home Inventory how many coffees are in the cold room"
- "Alexa, tell Home Inventory we used two coffees from the cold room"
- "Alexa, tell Home Inventory I put three cans of soup in the pantry"
- "Alexa, ask Home Inventory what's on the list"

It's a private custom skill in your own Amazon developer account. It isn't published, and it works on the Echo devices signed in to that Amazon account. Amazon sends what was said to `https://<your site>/alexa`, which already reaches the app through the Cloudflare Tunnel. Home Assistant isn't involved.

Each phrase has to name the skill ("ask Home Inventory ..."). "Alexa, add blueberries to the list" on its own always goes to Alexa's built-in shopping list, not this app.

## How it fits together

- `homeinv/alexa.py`: the `/alexa` endpoint, what each command does, and the Alexa page (More › Alexa).
- `homeinv/alexa_verify.py`: checks that each request really came from Amazon (signed with Amazon's certificate, for our skill ID, less than 150 seconds old). Amazon requires this, and it can't be turned off in production.
- `homeinv/alexa_model.py`: what can be said (the "interaction model"), built with the family's own item and place names so Alexa hears them better.
- Linking: Amazon tells the app which Amazon account is speaking, but not which family. On the Alexa page, someone gets a 6-digit code and says "Alexa, tell Home Inventory my code is ...". That account then works with that family until someone taps Unlink. The app stores only a hash of Amazon's account ID.

## Setting it up

### 1. Create the skill

1. Go to https://developer.amazon.com/alexa/console/ask and sign in with the **same Amazon account your Echo devices use**.
2. **Create Skill**:
   - **Name:** Home Inventory
   - **Primary locale:** the language your Echo devices are set to (Alexa app › Devices › your Echo › Language). For "English (Canada)" pick **English (CA)**. A mismatch means the Echo won't find the skill.
   - **Type of experience:** Other. **Model:** Custom. **Hosting:** Provision your own.
   - **Template:** Start from Scratch.
3. Copy the **Skill ID** (`amzn1.ask.skill.…`). It's on the console's skill list (View Skill ID) and on the Endpoint page.

### 2. Tell the app the skill ID

In Coolify, add the environment variable `ALEXA_SKILL_ID` = that ID and redeploy. Until it's set, `/alexa` answers 404 and the Alexa page shows a warning.

If you'd rather say something other than "Home Inventory", also set `ALEXA_INVOCATION_NAME` (lower case, e.g. `homey` or `our pantry`), then download and paste the interaction model again (step 3) so the console gets the same name. Amazon wants two words for published skills, but a private development skill can use one. If Alexa opens some other skill instead, pick a name nothing else uses.

### 3. Paste the interaction model

1. In the app: **More › Alexa › Setting up the skill › Download the interaction model**.
2. In the console: **Build › Interaction Model › JSON Editor**. Replace everything with the downloaded file, then **Save** and **Build skill**.

Do this again after adding a lot of new items or places, so Alexa knows the names. Words that aren't in the list still come through, just less reliably.

### 4. Point it at the app

**Build › Endpoint**:
- **Service endpoint type:** HTTPS
- **Default Region:** `https://home-inventory-dev.scrampy.cc/alexa` (the Alexa page shows the exact address)
- **SSL certificate type:** *My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority* (Cloudflare gives the site a wildcard certificate; the "trusted certificate authority" option makes the console say it can't reach the skill)

Save.

### 5. Try it in the console

**Test** tab: set "Skill testing is enabled in" to **Development**. Type `ask home inventory what's on the list`. The reply should be *This Alexa isn't linked to a family yet...*. That means Amazon reached the app and the request checks passed.

### 6. Link your Amazon account

In the app: **More › Alexa › Get a code**. Within 10 minutes, say to an Echo (or type in the Test tab): "Alexa, tell Home Inventory my code is 482193". It answers *Done. This Alexa is now linked to ...*.

Every Echo on that Amazon account now works. A family member with **their own** Amazon account needs the skill shared with them: **Distribution › Availability › Beta Test**, add their email, and once they accept they link with their own code. (The console may ask for a few store details before it allows a beta test.)

## If it doesn't work

- **The console says the endpoint can't be reached, or there's nothing in the app's log:** Cloudflare may be blocking Amazon. Bot Fight Mode, a WAF rule, or Cloudflare Access on the hostname can block automated POSTs. Allow the `/alexa` path.
- **The log shows `Refused an Alexa request: ...`:** a request arrived but failed a check. The message says which. `for another skill` means `ALEXA_SKILL_ID` doesn't match the console's Skill ID.
- **"Sorry, something went wrong in Home Inventory":** the log has the error, under `Alexa request failed`.
- **Alexa says the skill doesn't exist or opens something else:** check the skill's locale matches the Echo's language, and that testing is set to Development.
- **It mishears an item:** download and paste the interaction model again so it includes the item's name. Names that sound like common words work best.
