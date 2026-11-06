/**
 * Expo config. The site address comes from the environment, in this order:
 *   1. EXPO_PUBLIC_SITE_URL in mobile/.env (copy .env.example), e.g. http://192.168.1.20:8001
 *   2. SITE_URL in ../pita/.env (the Django settings), so the app follows the web app by default
 * The URL prefixes (auth, analyst panel, parent, child) are read the same way and must match Django.
 * When Guardian is hosted, set EXPO_PUBLIC_SITE_URL to the public https address and rebuild.
 */
const fs = require('fs');
const path = require('path');

function readDotenv(file) {
  try {
    return Object.fromEntries(
      fs.readFileSync(file, 'utf8').split(/\r?\n/)
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith('#') && l.includes('='))
        .map((l) => {
          const i = l.indexOf('=');
          return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^['"]|['"]$/g, '')];
        }),
    );
  } catch {
    return {};
  }
}

const django = readDotenv(path.join(__dirname, '..', 'pita', '.env'));
const env = (key, djangoKey, fallback) => process.env[key] || django[djangoKey] || fallback;

const siteUrl = env('EXPO_PUBLIC_SITE_URL', 'SITE_URL', 'http://localhost:8001').replace(/\/+$/, '');
const prefixes = {
  auth: env('EXPO_PUBLIC_AUTH_PREFIX', 'AWARENESS_AUTH_PREFIX', 'a4e2b1c9'),
  panel: env('EXPO_PUBLIC_PANEL_PREFIX', 'AWARENESS_PANEL_PREFIX', 'b2a9e6f1'),
  parent: env('EXPO_PUBLIC_PARENT_PREFIX', 'GUARDIAN_PARENT_PREFIX', 'family'),
  child: env('EXPO_PUBLIC_CHILD_PREFIX', 'GUARDIAN_CHILD_PREFIX', 'me'),
};
const host = (/^https?:\/\/([^/:]+)/i.exec(siteUrl) || [])[1] || 'localhost';
const https = siteUrl.startsWith('https://');

// Practice links, "stop" links and password resets open straight in the app once the site is on https.
const linkFilters = https ? [{
  action: 'VIEW',
  autoVerify: true,
  data: ['/p/', '/stop/', `/${prefixes.auth}/password/reset/`].map((pathPrefix) => ({ scheme: 'https', host, pathPrefix })),
  category: ['BROWSABLE', 'DEFAULT'],
}] : [];

module.exports = {
  expo: {
    name: 'Guardian',
    slug: 'guardian-child-safety',
    scheme: 'guardian',
    version: '1.0.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    userInterfaceStyle: 'automatic',
    ios: {
      supportsTablet: true,
      bundleIdentifier: 'ug.guardian.childsafety',
      associatedDomains: https ? [`applinks:${host}`] : [],
      infoPlist: { NSPhotoLibraryUsageDescription: 'Choose a screenshot to check whether a message is safe.',
                   NSCameraUsageDescription: 'Take a photo of a message to check whether it is safe.' },
    },
    android: {
      package: 'ug.guardian.childsafety',
      versionCode: 1,
      adaptiveIcon: { foregroundImage: './assets/icon.png', backgroundColor: '#003732' },
      intentFilters: linkFilters,
    },
    plugins: [
      './plugins/with-short-native-paths',
      // The server is chosen on device; LAN development connections can use HTTP.
      ['expo-build-properties', { android: { usesCleartextTraffic: true } }],
      ['expo-image-picker', { cameraPermission: 'Take a photo of a message to check whether it is safe.', microphonePermission: false }],
    ],
    extra: { siteUrl, prefixes },
  },
};
