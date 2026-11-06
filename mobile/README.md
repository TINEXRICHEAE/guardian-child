# Guardian native mobile app

React Native / Expo SDK 58 client for the existing Guardian Django application.
All changes for this client live in `mobile/`. The app no longer uses a WebView or
executes website JavaScript. Text, cards, inputs, checkboxes, radio groups,
selectors, tables, navigation and uploads use React Native controls.

## Install on Android

Download the APK from the [Android 1.0.0 preview release](https://github.com/TINEXRICHEAE/guardian-child/releases/tag/android-v1.0.0-preview).

The shareable build is `build/Guardian.apk` after a successful local release build.
Send that file to the phone, open it, and allow installation from the app used to
open the file. This is a sideload build rather than a Play Store release.
The JavaScript bundle is included; Metro, Expo Go and a USB cable are not required.

On first launch, tap **Connect to Guardian** and enter your running Guardian
website's base URL. Connection settings are saved on the device. Use HTTPS for a
shared deployment. The app needs internet access to that backend for accounts,
family records, lessons and AI checks; those services are not bundled into the APK.
The welcome and connection screens are available without a server.

For local testing, use the computer's Wi-Fi IP and Django port, for example
`http://192.168.1.20:8001`. The phone must be on the same network, Django must listen
on all interfaces, and the server must allow that host. Local HTTP also requires
the backend's development cookie configuration. `localhost` and `10.0.2.2` are
rejected in phone connection settings because they do not reach a laptop from a
physical phone. Route prefixes must match the deployment; defaults match this repo.

## How it connects

The backend provides JSON account APIs but its other workflows return HTML rather
than a public mobile JSON API. To keep the backend unchanged:

- `src/client.js` uses the existing session cookies, CSRF endpoint and form actions.
- `src/pageModel.js` parses server responses into content and form data.
- `src/NativePage.js` presents that content using native components and submits
  forms through the client. It never runs server-supplied scripts.
- `src/NativeAccount.js` uses the existing JSON profile and account endpoints.
- `App.js` provides server setup, saved connection settings, theme, history,
  native role tabs, external-link confirmation and deep-link handling.

This adapter covers the server-rendered family management/consent, family codes,
news and practice forms, message/link/screenshot checks, reports, lessons/quizzes,
alerts, settings, password pages, analyst sources/content/campaigns, analytics
tables and evaluation forms. Source type selection and approve/reject hidden forms
have explicit native handling. Backend permissions and privacy rules still apply.
Account editing and picture upload use native screens. Google OAuth has no native
callback integration: use email/password or the password-reset flow.

### Current limits

This is a native client over existing server responses, not an independent offline
copy of Django or its AI models. It depends on the current HTML form structure.
Website JavaScript is not ported automatically. Browser print/PDF export remains
available through the header's browser button. JavaScript canvas charts are not
rendered natively; server-rendered figures and tables remain available. Evaluation
progress can be refreshed by pulling down. Complete feature parity requires live
testing against the target deployment and native replacements for any additional
browser-only interactions. A successful build alone does not verify those flows.

## Development and builds

Requires Node >=22.13, Java 21 and the Android SDK components required by Expo SDK
58 / React Native 0.88. Install dependencies with `npm ci`, then:

```powershell
npm test
npx expo export --platform android --output-dir build/bundle-check
npx expo prebuild --platform android --no-install
$env:ANDROID_HOME = 'C:\path\to\android-sdk'
cd android
.\gradlew.bat assembleRelease --no-daemon '-PreactNativeArchitectures=arm64-v8a,armeabi-v7a'
cd ..
Copy-Item android/app/build/outputs/apk/release/app-release.apk build/Guardian.apk
```

The generated Android project and build outputs are ignored by Git. The local
config plugin in `plugins/with-short-native-paths.js` hashes long C++ object paths
to keep Windows builds within Ninja's path limit. Expo's local
release template signs with its development key, which is adequate for testing and
sideloading. Use a separately managed private release key before public distribution
or publishing updates. The EAS `preview` profile also requests an installable APK;
`production` requests a Play Store app bundle and needs your Expo account setup.

Only the connection address and route prefixes are stored by this client. Session
cookies are managed by React Native's native networking. Passwords and checked
messages are not persisted in AsyncStorage.
