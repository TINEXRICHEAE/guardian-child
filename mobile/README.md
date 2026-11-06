# Guardian mobile app

A React Native (Expo SDK 58) app for Android and iPhone. It mirrors the Guardian Django site: every page is the
live site shown inside the app, with native tabs, link handling and offline screens. Any change to the web app
appears in the mobile app straight away, with no app update needed.

## What the app adds around the site

| | |
|---|---|
| **Native tabs by role** | Signed out: Home, Sign in, Join, Family code, Get help. Child: My space, Is this safe?, Lessons, Report, Get help. Parent: Family, News, Check, Alerts, Settings. Analyst: Dashboard, Content, Campaigns, Analytics, Models. The app learns the role from the signed-in page, then switches tabs. |
| **No duplicate menus** | The website's own bottom tab bar and footer are hidden inside the app. |
| **Links** | Guardian pages open in the app. Call 116, email and SMS links open the phone's dialler or mail app. Other websites open in the phone's browser. |
| **Practice and reset links** | Once the site is on https, practice-email links (`/p/…`), stop links and password-reset links open straight in the app (Android App Links, iOS associated domains). `guardian://p/TOKEN` works in development. |
| **Google sign-in** | Google blocks its sign-in inside embedded web views. The app explains this and offers **Set a password** instead, which uses Guardian's email reset and works for Google-only accounts too. |
| **Phone behaviour** | Android back button walks back through pages, loading bar, pull to refresh (iPhone), screenshot upload from the gallery or camera, dark mode follows the site. |
| **Offline** | A clear "Guardian can't be reached" screen with Try again and Call 116. |

## Where the site address comes from

`app.config.js` reads, in this order:

1. `EXPO_PUBLIC_SITE_URL` in `mobile/.env` (copy `.env.example`);
2. `SITE_URL` in `../pita/.env`, so the app follows the Django settings by default.

The URL prefixes (`AWARENESS_AUTH_PREFIX`, `AWARENESS_PANEL_PREFIX`, `GUARDIAN_PARENT_PREFIX`,
`GUARDIAN_CHILD_PREFIX`) are read the same way and must match Django. Check what the app will use with
`npm run config`.

**When Guardian is hosted:** set `EXPO_PUBLIC_SITE_URL=https://your-domain` and rebuild. Plain http is only
allowed while the address is not https.

## Run it

Expo SDK 58 needs **Node 22.13 or newer**. The bundle builds on Node 20, but the Expo CLI warns about it.

```bash
cd mobile
npm install
cp .env.example .env        # then set EXPO_PUBLIC_SITE_URL
npm start                   # scan the QR code with a development build, or press "a" for the Android emulator
npm test                    # routing and link rules, no phone needed
```

**Testing on a real phone against the laptop.** On the phone, `localhost` means the phone itself:

1. Find the laptop's Wi-Fi address, for example `192.168.1.20`.
2. In `pita/.env` set `ALLOWED_HOST=192.168.1.20`. It takes a comma-separated list if you need several.
3. Run Django on all interfaces: `python manage.py runserver 0.0.0.0:8001`.
4. In `mobile/.env` set `EXPO_PUBLIC_SITE_URL=http://192.168.1.20:8001`.

The Android emulator reaches the laptop's `localhost` by itself: the app rewrites it to `10.0.2.2`.

Because the app includes native modules (`react-native-webview`, build properties), use a development build
(`npx expo run:android`) or an EAS build rather than Expo Go:

```bash
npx eas build --profile preview --platform android     # installable APK
npx eas build --profile production --platform android  # Play Store bundle
```

## Files

| File | Purpose |
|---|---|
| `App.js` | The web view, tabs, link rules, deep links, back button, offline screen |
| `src/routes.js` | Pure routing rules (tabs per role, link classification, deep links), tested in `tests/` |
| `src/bridge.js` | Script run inside each page: hides the site's own tab bar and footer, reports role and dark mode |
| `src/TabBar.js`, `src/OfflineScreen.js`, `src/theme.js` | Native UI in Guardian's colours |
| `app.config.js` | App name, icon, deep links, and the site address from `.env` |

The app sends nothing about page content to native code: only the signed-in role and whether dark mode is on.
