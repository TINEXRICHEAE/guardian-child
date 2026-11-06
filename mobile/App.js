import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, BackHandler, Linking, Platform, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';
import Constants from 'expo-constants';

import { activeTab, classify, deepLinkPath, forEmulator, pathOf, tabsFor } from './src/routes';
import TabBar from './src/TabBar';
import OfflineScreen from './src/OfflineScreen';
import { BRIDGE_JS } from './src/bridge';
import { colors } from './src/theme';

const extra = Constants.expoConfig?.extra || {};
const SITE_URL = forEmulator(extra.siteUrl || 'http://localhost:8001', Platform.OS === 'android');
const PREFIXES = extra.prefixes;

export default function App() {
  return (
    <SafeAreaProvider>
      <Guardian />
    </SafeAreaProvider>
  );
}

function Guardian() {
  const web = useRef(null);
  const [startPath, setStartPath] = useState(null);
  const [role, setRole] = useState(undefined);         // undefined = not known yet, null = signed out
  const [path, setPath] = useState('/');
  const [canGoBack, setCanGoBack] = useState(false);
  const [progress, setProgress] = useState(0);
  const [failed, setFailed] = useState(null);
  const [dark, setDark] = useState(false);

  const tabs = useMemo(() => tabsFor(role === undefined ? null : role, PREFIXES), [role]);
  const current = activeTab(tabs, path);

  const go = useCallback((sitePath) => {
    const url = SITE_URL + sitePath;
    setFailed(null);
    web.current?.injectJavaScript(`window.location.href = ${JSON.stringify(url)}; true;`);
  }, []);

  // Deep links: a practice link, a "stop" link or a password reset tapped in an email opens here.
  useEffect(() => {
    Linking.getInitialURL().then((u) => setStartPath(deepLinkPath(u, SITE_URL) || '/'));
    const sub = Linking.addEventListener('url', ({ url }) => {
      const p = deepLinkPath(url, SITE_URL);
      if (p) go(p);
    });
    return () => sub.remove();
  }, [go]);

  // Android back button walks back through the site before leaving the app.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (canGoBack) {
        web.current?.goBack();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [canGoBack]);

  const onShouldStart = useCallback((req) => {
    if (req.isTopFrame === false) return true;                   // e.g. the email preview frame
    const kind = classify(req.url, SITE_URL);
    if (kind === 'web') return true;
    if (kind === 'google') {
      Alert.alert(
        'Google sign-in opens outside the app',
        'Google does not allow its sign-in inside apps like this one. Sign in with your email and password instead. '
          + 'If you only used Google so far, choose "Set a password" and Guardian emails you a link to add one.',
        [{ text: 'Not now', style: 'cancel' },
         { text: 'Set a password', onPress: () => go(`/${PREFIXES.auth}/password/reset/`) }],
      );
      return false;
    }
    Linking.openURL(req.url).catch(() => Alert.alert('Could not open this link', req.url));
    return false;
  }, [go]);

  const onMessage = useCallback((e) => {
    try {
      const msg = JSON.parse(e.nativeEvent.data);
      if (msg.type === 'page') {
        setRole(msg.role || null);
        setDark(!!msg.dark);
      } else if (msg.type === 'theme') {
        setDark(!!msg.dark);
      }
    } catch {
      // not ours
    }
  }, []);

  if (startPath === null) return <View style={[styles.fill, { backgroundColor: colors.primary }]} />;

  return (
    <SafeAreaView style={[styles.fill, { backgroundColor: colors.primary }]} edges={['top']}>
      <StatusBar style="light" />
      <View style={[styles.fill, { backgroundColor: dark ? colors.darkBg : colors.lightBg }]}>
        {progress > 0 && progress < 1 && <View style={[styles.progress, { width: `${progress * 100}%` }]} />}
        {failed ? (
          <OfflineScreen siteUrl={SITE_URL} detail={failed} onRetry={() => { setFailed(null); web.current?.reload(); }} />
        ) : null}
        <WebView
          ref={web}
          style={[styles.fill, failed ? styles.hidden : null]}
          source={{ uri: SITE_URL + startPath }}
          originWhitelist={['*']}
          applicationNameForUserAgent="GuardianApp/1.0"
          injectedJavaScript={BRIDGE_JS}
          onMessage={onMessage}
          onShouldStartLoadWithRequest={onShouldStart}
          onNavigationStateChange={(nav) => { setCanGoBack(nav.canGoBack); setPath(pathOf(nav.url, SITE_URL)); }}
          onLoadProgress={({ nativeEvent }) => setProgress(nativeEvent.progress)}
          onError={({ nativeEvent }) => setFailed(nativeEvent.description || 'The page could not load.')}
          sharedCookiesEnabled
          thirdPartyCookiesEnabled
          domStorageEnabled
          javaScriptEnabled
          allowsBackForwardNavigationGestures
          pullToRefreshEnabled
          setSupportMultipleWindows={false}
          allowFileAccess
          mediaCapturePermissionGrantType="prompt"
        />
      </View>
      <TabBar tabs={tabs} active={current} dark={dark}
              onPress={(t) => go(t.path)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  hidden: { display: 'none' },
  progress: { height: 3, backgroundColor: colors.accent, position: 'absolute', top: 0, left: 0, zIndex: 10 },
});
