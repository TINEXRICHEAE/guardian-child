/**
 * Expo config. The server address is built into the app (plan.md §20): nobody types it on the phone.
 *   - guardian.server.json (committed) holds the address and route prefixes: edit it when the server moves.
 *   - EXPO_PUBLIC_SITE_URL, if set when building, overrides it (developers testing a laptop on Wi-Fi).
 */
const server = require('./guardian.server.json');

const siteUrl = (process.env.EXPO_PUBLIC_SITE_URL || server.siteUrl).replace(/\/+$/, '');
const prefixes = { ...server.prefixes };
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
      // Plain http is allowed only when the built-in address is http (a laptop during development).
      ['expo-build-properties', { android: { usesCleartextTraffic: !https } }],
      ['expo-image-picker', { cameraPermission: 'Take a photo of a message to check whether it is safe.', microphonePermission: false }],
    ],
    extra: { siteUrl, prefixes },
  },
};
