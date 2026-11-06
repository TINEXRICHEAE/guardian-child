import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, BackHandler, Linking, Modal, Pressable, RefreshControl, ScrollView, StyleSheet, Text, useColorScheme, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { GuardianClient } from './src/client';
import NativePage, { Button } from './src/NativePage';
import { DEFAULT_PREFIXES, tabsFor, activeTab, deepLinkPath } from './src/routes';
import { siteAddress } from './src/pageModel';
import TabBar from './src/TabBar';
import NativeAccount from './src/NativeAccount';

const config = Constants.expoConfig?.extra || {};
// The server address is built into the app from guardian.server.json (plan.md §20); it is never typed on the phone.
const OLD_STORAGE_KEY = 'guardian.connection.v1';      // address saved by earlier builds: ignored and removed
const CONNECTION = (() => {
  try { return { site: siteAddress(config.siteUrl || ''), prefixes: { ...DEFAULT_PREFIXES, ...config.prefixes } }; }
  catch { return null; }
})();
export default function App() { return <SafeAreaProvider><Guardian /></SafeAreaProvider>; }
function Guardian() {
  const dark = useColorScheme() === 'dark';
  const palette = dark ? { bg: '#0d1615', card: '#1a2423', text: '#e2eeeb', muted: '#9abbb5', line: '#344c47', accent: '#58cbb8', error: '#ffb4ab', selected: '#244b42' }
    : { bg: '#f3f7f5', card: '#fff', text: '#153d34', muted: '#587068', line: '#d4e2db', accent: '#007966', error: '#ba1a1a', selected: '#dff4ea' };
  const connection = CONNECTION;
  const [page, setPage] = useState(null), [profile, setProfile] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const [revision, setRevision] = useState(0);
  const [account, setAccount] = useState(false);
  const history = useRef([]), scroll = useRef(null), requestId = useRef(0), pageRef = useRef(null);
  const client = useMemo(() => connection ? new GuardianClient(connection.site, connection.prefixes) : null, [connection]);
  const tabs = tabsFor(profile?.role, connection?.prefixes);
  const currentPath = page?.url ? new URL(page.url).pathname : '/';
  const updateProfile = useCallback(async () => {
    if (!client) return;
    try { setProfile(await client.profile()); } catch { /* Retry on the next navigation. */ }
  }, [client]);
  function acceptPage(result, replace) {
    if (!replace && pageRef.current) history.current.push(pageRef.current.url);
    pageRef.current = result; setPage(result); setRevision((n) => n + 1); scroll.current?.scrollTo({ y: 0, animated: false });
  }
  const load = useCallback(async (target, { replace = false } = {}) => {
    if (!client) return;
    const url = new URL(target, pageRef.current?.url || client.site);
    if (['tel:', 'mailto:', 'sms:'].includes(url.protocol)) { Linking.openURL(url.href).catch(() => {}); return; }
    if (!['http:', 'https:'].includes(url.protocol)) return;
    if (url.origin !== client.site) {
      Alert.alert('Open external website?', url.hostname, [{ text: 'Cancel', style: 'cancel' }, { text: 'Open browser', onPress: () => Linking.openURL(url.href).catch(() => {}) }]); return;
    }
    if (url.pathname.includes('/accounts/google/')) {
      Alert.alert('Sign in with a password', 'Use your Guardian email and password. If you originally used Google, set a password using the reset link.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Set a password', onPress: () => load(`/${connection.prefixes.auth}/password/reset/`) }]); return;
    }
    const id = ++requestId.current;
    setBusy(true); setError(null);
    try {
      const result = await client.request(url.href);
      if (id !== requestId.current) return;
      if (result.json) { Alert.alert('Guardian', result.json.message || JSON.stringify(result.json)); return; }
      acceptPage(result, replace); await updateProfile();
    } catch (e) { if (id === requestId.current) setError(e.message || 'Cannot connect to Guardian.'); }
    finally { if (id === requestId.current) setBusy(false); }
  }, [client, connection, updateProfile]);
  useEffect(() => { AsyncStorage.removeItem(OLD_STORAGE_KEY).catch(() => {}); }, []);
  useEffect(() => { if (client) { pageRef.current = null; history.current = []; setPage(null); setProfile(null); load('/'); } }, [client]);
  useEffect(() => {
    const open = ({ url }) => { if (client) { const path = deepLinkPath(url, client.site); if (path) load(path); } };
    Linking.getInitialURL().then((url) => { if (url) open({ url }); });
    const sub = Linking.addEventListener('url', open); return () => sub.remove();
  }, [client, load]);
  function back() { const previous = history.current.pop(); if (previous) { load(previous, { replace: true }); return true; } return false; }
  useEffect(() => { const sub = BackHandler.addEventListener('hardwareBackPress', back); return () => sub.remove(); }, [load]);
  async function submit(form, values, submitter) {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const result = await client.submit(form, values, submitter, page.url);
      if (result.json) { Alert.alert('Guardian', result.json.message || 'Saved successfully.'); await load(page.url, { replace: true }); }
      else { acceptPage(result, false); await updateProfile(); }
    } finally { setBusy(false); }
  }
  return <SafeAreaView style={[s.fill, { backgroundColor: palette.bg }]} edges={['top']}>
    <StatusBar style={dark ? 'light' : 'dark'} />
    <View style={[s.header, { borderColor: palette.line, backgroundColor: palette.card }]}>
      <Pressable onPress={back} accessibilityLabel="Go back" style={s.icon}><Ionicons name="shield-checkmark" size={28} color={palette.accent} /></Pressable>
      <View style={s.fill}><Text style={[s.brand, { color: palette.text }]}>Guardian</Text><Text style={{ color: palette.muted, fontSize: 12 }}>{profile?.role ? `${profile.role} space` : 'Safer online, together'}</Text></View>
      {profile && <Pressable accessibilityLabel="Your account" onPress={() => setAccount(true)} style={s.icon}><Ionicons name="person-circle-outline" size={24} color={palette.accent} /></Pressable>}
      <Pressable accessibilityLabel="Open current page in browser" onPress={() => page && Linking.openURL(page.url)} style={s.icon}><Ionicons name="open-outline" size={21} color={palette.accent} /></Pressable>
    </View>
    <ScrollView ref={scroll} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled" refreshControl={<RefreshControl refreshing={busy} onRefresh={() => load(page?.url || '/', { replace: true })} tintColor={palette.accent} />}>
      {!connection && <View style={s.hero}><Ionicons name="shield-checkmark-outline" size={64} color={palette.accent} /><Text style={[s.title, { color: palette.text }]}>Guardian is not set up in this build.</Text><Text style={[s.copy, { color: palette.muted }]}>The app was built without a valid server address. Set siteUrl in mobile/guardian.server.json and build again.</Text></View>}
      {error && <View style={[s.notice, { backgroundColor: palette.card, borderColor: palette.error }]}><Text accessibilityRole="alert" style={{ color: palette.error }}>{error}</Text><Button title="Try again" palette={palette} onPress={() => load(page?.url || '/', { replace: true })} /></View>}
      {connection && !page && busy && <ActivityIndicator color={palette.accent} size="large" style={s.center} />}
      {profile?.role === 'analyst' && <View style={s.shortcuts}>{['sources', 'raw', 'content', 'campaigns', 'analytics', 'evaluation'].map((p) => <Pressable key={p} onPress={() => load(`/${connection.prefixes.panel}/${p}/`)}><Text style={{ color: palette.accent, padding: 9 }}>{p[0].toUpperCase() + p.slice(1)}</Text></Pressable>)}</View>}
      {page && <NativePage key={revision} page={page} onNavigate={load} onSubmit={submit} busy={busy} palette={palette} />}
      {profile && <Button title="Sign out" palette={palette} secondary disabled={busy} onPress={() => submit({ attribs: { method: 'post', action: `/${connection.prefixes.auth}/logout/` } }, {}, {}).then(() => load('/')).catch((e) => setError(e.message))} />}
      <Text style={[s.copy, { color: palette.muted, marginTop: 28 }]}>Need urgent help?</Text><Button title="Call 116" palette={palette} secondary onPress={() => Linking.openURL('tel:116').catch(() => {})} />
    </ScrollView>
    <TabBar tabs={tabs} active={activeTab(tabs, currentPath)} dark={dark} onPress={(tab) => { if (!busy) load(tab.path); }} />
    <Modal visible={account && !!profile} animationType="slide" onRequestClose={() => setAccount(false)}><SafeAreaView style={[s.fill, { backgroundColor: palette.bg }]}>{profile && <NativeAccount profile={profile} client={client} palette={palette} onRefresh={updateProfile} onClose={() => setAccount(false)} onSecurity={() => { setAccount(false); load(`/${connection.prefixes.auth}/security/`); }} onDeleted={() => { setAccount(false); setProfile(null); load('/'); }} />}</SafeAreaView></Modal>
  </SafeAreaView>;
}
const s = StyleSheet.create({ fill: { flex: 1 }, header: { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10, borderBottomWidth: 1 }, icon: { padding: 8 }, brand: { fontSize: 22, fontWeight: '800' }, content: { padding: 20, paddingBottom: 36, gap: 14 }, center: { marginTop: 70 }, hero: { gap: 18, paddingVertical: 24 }, title: { fontSize: 33, lineHeight: 40, fontWeight: '800' }, subtitle: { fontSize: 20, fontWeight: '700', marginTop: 16 }, copy: { fontSize: 15, lineHeight: 24 }, input: { borderWidth: 1, padding: 15, borderRadius: 12, fontSize: 16 }, notice: { padding: 16, borderWidth: 1, borderRadius: 16, gap: 12 }, shortcuts: { flexDirection: 'row', flexWrap: 'wrap' } });
